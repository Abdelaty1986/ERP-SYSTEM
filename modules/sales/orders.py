from flask import flash, redirect, render_template, request, url_for


def _order_lines_from_form(cur, deps):
    parse_positive_amount = deps["parse_positive_amount"]
    default_tax_rate = deps["DEFAULT_TAX_RATE"]
    product_ids = request.form.getlist("product_id[]") or request.form.getlist("product_id")
    quantities = request.form.getlist("quantity[]") or request.form.getlist("quantity")
    unit_prices = request.form.getlist("unit_price[]") or request.form.getlist("unit_price")
    tax_rates = request.form.getlist("tax_rate[]") or request.form.getlist("tax_rate")
    lines = []
    for idx, product_id in enumerate(product_ids):
        product_id = (product_id or "").strip()
        quantity = parse_positive_amount(quantities[idx] if idx < len(quantities) else 0)
        unit_price = parse_positive_amount(unit_prices[idx] if idx < len(unit_prices) else 0)
        tax_rate = parse_positive_amount(tax_rates[idx] if idx < len(tax_rates) else default_tax_rate)
        if not product_id and quantity == 0 and unit_price == 0:
            continue
        cur.execute("SELECT 1 FROM products WHERE id=?", (product_id,))
        if not cur.fetchone() or quantity <= 0 or unit_price <= 0:
            return []
        total = quantity * unit_price
        tax_amount = total * tax_rate / 100
        lines.append((int(product_id), quantity, unit_price, total, tax_rate, tax_amount, total + tax_amount))
    return lines


def build_sales_orders_view(deps):
    db = deps["db"]
    parse_iso_date = deps["parse_iso_date"]
    log_action = deps["log_action"]

    def sales_orders():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            customer_id = request.form.get("customer_id") or None
            payment_terms = request.form.get("payment_terms", "").strip()
            delivery_date = request.form.get("delivery_date", "").strip()
            notes = request.form.get("notes", "").strip()
            lines = _order_lines_from_form(cur, deps)
            order_date = parse_iso_date(date_value)
            requested_delivery = parse_iso_date(delivery_date)
            if not date_value:
                flash("تاريخ أمر البيع مطلوب.", "danger")
            elif requested_delivery and order_date and requested_delivery < order_date:
                flash("تاريخ التسليم لا يمكن أن يكون أسبق من تاريخ أمر البيع.", "danger")
            elif not lines:
                flash("أضف صنفًا واحدًا على الأقل بكمية وسعر صحيحين.", "danger")
            else:
                total = sum(line[3] for line in lines)
                tax_amount = sum(line[5] for line in lines)
                grand_total = sum(line[6] for line in lines)
                quantity = sum(line[1] for line in lines)
                first_line = lines[0]
                cur.execute(
                    """
                    INSERT INTO sales_orders(date,customer_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total,payment_terms,delivery_date,notes,status)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        date_value,
                        customer_id,
                        first_line[0],
                        quantity,
                        total / quantity if quantity else first_line[2],
                        total,
                        first_line[4],
                        tax_amount,
                        grand_total,
                        payment_terms,
                        delivery_date,
                        notes,
                        "issued",
                    ),
                )
                order_id = cur.lastrowid
                for line in lines:
                    cur.execute(
                        "INSERT INTO sales_order_lines(order_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total) VALUES (?,?,?,?,?,?,?,?)",
                        (order_id, *line),
                    )
                log_action(cur, "create", "sales_order", order_id, f"lines={len(lines)}; total={grand_total}")
                conn.commit()
                conn.close()
                flash("تم حفظ أمر البيع متعدد الأصناف.", "success")
                return redirect(url_for("sales_orders"))

        cur.execute("SELECT id,name FROM customers ORDER BY name")
        customers_rows = cur.fetchall()
        cur.execute("SELECT id,name,sale_price,stock_quantity FROM products ORDER BY name")
        product_rows = cur.fetchall()
        cur.execute(
            """
            SELECT so.id,so.date,COALESCE(c.name,'بيع نقدي'),COUNT(sol.id),so.quantity,so.grand_total,so.delivery_date,so.status
            FROM sales_orders so
            LEFT JOIN customers c ON c.id=so.customer_id
            LEFT JOIN sales_order_lines sol ON sol.order_id=so.id
            GROUP BY so.id
            ORDER BY so.id DESC
            """
        )
        base_rows = cur.fetchall()
        rows = []
        for row in base_rows:
            cur.execute(
                """
                SELECT p.name,sol.quantity
                FROM sales_order_lines sol
                JOIN products p ON p.id=sol.product_id
                WHERE sol.order_id=?
                ORDER BY sol.id
                """,
                (row[0],),
            )
            summary = " / ".join(f"{name} ({qty:g})" for name, qty in cur.fetchall())
            rows.append((row[0], row[1], row[2], summary, row[3], row[4], row[5], row[6], row[7]))
        conn.close()
        return render_template("sales_orders.html", customers=customers_rows, products=product_rows, rows=rows)

    return sales_orders


def build_purchase_orders_view(deps):
    db = deps["db"]
    parse_iso_date = deps["parse_iso_date"]
    log_action = deps["log_action"]

    def purchase_orders():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            supplier_id = request.form.get("supplier_id")
            payment_terms = request.form.get("payment_terms", "").strip()
            delivery_date = request.form.get("delivery_date", "").strip()
            delivery_terms = request.form.get("delivery_terms", "").strip()
            notes = request.form.get("notes", "").strip()
            lines = _order_lines_from_form(cur, deps)
            order_date = parse_iso_date(date_value)
            requested_delivery = parse_iso_date(delivery_date)
            cur.execute("SELECT 1 FROM suppliers WHERE id=?", (supplier_id,))
            supplier = cur.fetchone()
            if not date_value:
                flash("تاريخ أمر الشراء مطلوب.", "danger")
            elif not supplier:
                flash("اختر المورد.", "danger")
            elif requested_delivery and order_date and requested_delivery < order_date:
                flash("تاريخ التوريد لا يمكن أن يكون أسبق من تاريخ أمر الشراء.", "danger")
            elif not lines:
                flash("أضف صنفًا واحدًا على الأقل بكمية وسعر صحيحين.", "danger")
            else:
                total = sum(line[3] for line in lines)
                tax_amount = sum(line[5] for line in lines)
                grand_total = sum(line[6] for line in lines)
                quantity = sum(line[1] for line in lines)
                first_line = lines[0]
                cur.execute(
                    """
                    INSERT INTO purchase_orders(date,supplier_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total,payment_terms,delivery_date,delivery_terms,notes,status)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        date_value,
                        supplier_id,
                        first_line[0],
                        quantity,
                        total / quantity if quantity else first_line[2],
                        total,
                        first_line[4],
                        tax_amount,
                        grand_total,
                        payment_terms,
                        delivery_date,
                        delivery_terms,
                        notes,
                        "issued",
                    ),
                )
                order_id = cur.lastrowid
                for line in lines:
                    cur.execute(
                        "INSERT INTO purchase_order_lines(order_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total) VALUES (?,?,?,?,?,?,?,?)",
                        (order_id, *line),
                    )
                log_action(cur, "create", "purchase_order", order_id, f"lines={len(lines)}; total={grand_total}")
                conn.commit()
                conn.close()
                flash("تم حفظ أمر الشراء متعدد الأصناف.", "success")
                return redirect(url_for("purchase_orders"))

        cur.execute("SELECT id,name FROM suppliers ORDER BY name")
        suppliers_rows = cur.fetchall()
        cur.execute("SELECT id,name,purchase_price,stock_quantity FROM products ORDER BY name")
        product_rows = cur.fetchall()
        cur.execute(
            """
            SELECT po.id,po.date,s.name,COUNT(pol.id),po.quantity,po.grand_total,po.payment_terms,po.delivery_date,po.status
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id=s.id
            LEFT JOIN purchase_order_lines pol ON pol.order_id=po.id
            GROUP BY po.id
            ORDER BY po.id DESC
            """
        )
        base_rows = cur.fetchall()
        orders = []
        for row in base_rows:
            cur.execute(
                """
                SELECT p.name,pol.quantity
                FROM purchase_order_lines pol
                JOIN products p ON p.id=pol.product_id
                WHERE pol.order_id=?
                ORDER BY pol.id
                """,
                (row[0],),
            )
            summary = " / ".join(f"{name} ({qty:g})" for name, qty in cur.fetchall())
            orders.append((row[0], row[1], row[2], summary, row[3], row[4], row[5], row[6], row[7], row[8]))
        conn.close()
        return render_template("purchase_orders.html", suppliers=suppliers_rows, products=product_rows, orders=orders)

    return purchase_orders


def build_print_purchase_order_view(deps):
    db = deps["db"]
    get_company_settings = deps["get_company_settings"]

    def print_purchase_order(id):
        conn = db()
        cur = conn.cursor()
        company = get_company_settings(cur)
        cur.execute(
            """
            SELECT po.id,po.date,s.name,COALESCE(s.phone,''),COALESCE(s.address,''),
                   po.payment_terms,po.delivery_date,po.delivery_terms,po.status,po.notes,
                   po.total,po.tax_amount,po.grand_total
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id=s.id
            WHERE po.id=?
            """,
            (id,),
        )
        order = cur.fetchone()
        cur.execute(
            """
            SELECT p.name,p.unit,pol.quantity,pol.unit_price,pol.total,pol.tax_amount,pol.grand_total
            FROM purchase_order_lines pol
            JOIN products p ON p.id=pol.product_id
            WHERE pol.order_id=?
            ORDER BY pol.id
            """,
            (id,),
        )
        lines = cur.fetchall()
        conn.close()
        if not order:
            flash("أمر الشراء غير موجود.", "danger")
            return redirect(url_for("purchase_orders"))
        return render_template("print_purchase_order.html", company=company, order=order, lines=lines)

    return print_purchase_order
