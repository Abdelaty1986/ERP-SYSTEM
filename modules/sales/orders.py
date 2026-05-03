import json

from flask import flash, redirect, render_template, request, url_for


def _ensure_product_unit_mapping(cur, product_id):
    cur.execute("SELECT unit,purchase_price,sale_price FROM products WHERE id=?", (product_id,))
    product = cur.fetchone()
    if not product:
        return
    cur.execute("SELECT COUNT(*) FROM product_units WHERE product_id=?", (product_id,))
    if cur.fetchone()[0]:
        return
    cur.execute(
        """
        INSERT OR IGNORE INTO measurement_units(name, code, description, is_active)
        VALUES ('وحدة','UNIT','وحدة عامة للاستخدام الافتراضي',1)
        """
    )
    cur.execute("SELECT id FROM measurement_units WHERE name='وحدة'")
    unit_id = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO product_units(
            product_id,unit_id,conversion_factor,purchase_price,sale_price,
            is_default_purchase,is_default_sale,is_base_unit,is_active
        )
        VALUES (?,?,?,?,?,1,1,1,1)
        """,
        (product_id, unit_id, 1, float(product[1] or 0), float(product[2] or 0)),
    )
    cur.execute("UPDATE products SET unit=? WHERE id=?", (product[0] or "وحدة", product_id))


def _resolve_product_unit(cur, product_id, selected_unit_id=None, purpose="sale"):
    _ensure_product_unit_mapping(cur, product_id)
    order_column = "pu.is_default_sale" if purpose == "sale" else "pu.is_default_purchase"
    params = [product_id]
    selected_clause = ""
    if selected_unit_id:
        selected_clause = " AND pu.unit_id=?"
        params.append(int(selected_unit_id))
    cur.execute(
        f"""
        SELECT pu.unit_id,mu.name,pu.conversion_factor,pu.purchase_price,pu.sale_price,
               pu.is_default_purchase,pu.is_default_sale,pu.is_base_unit
        FROM product_units pu
        JOIN measurement_units mu ON mu.id=pu.unit_id
        WHERE pu.product_id=? AND pu.is_active=1{selected_clause}
        ORDER BY {order_column} DESC, pu.is_base_unit DESC, pu.id ASC
        LIMIT 1
        """,
        params,
    )
    row = cur.fetchone()
    if row:
        return {
            "unit_id": row[0],
            "unit_name": row[1],
            "conversion_factor": float(row[2] or 1),
            "purchase_price": float(row[3] or 0),
            "sale_price": float(row[4] or 0),
            "is_default_purchase": bool(row[5]),
            "is_default_sale": bool(row[6]),
            "is_base_unit": bool(row[7]),
        }
    return {
        "unit_id": None,
        "unit_name": "وحدة",
        "conversion_factor": 1.0,
        "purchase_price": 0.0,
        "sale_price": 0.0,
        "is_default_purchase": True,
        "is_default_sale": True,
        "is_base_unit": True,
    }


def _build_product_units_map(cur, purpose="sale"):
    cur.execute("SELECT id,name,stock_quantity,purchase_price,sale_price FROM products ORDER BY name")
    raw_product_rows = cur.fetchall()
    product_rows = []
    data = {}
    for product_id, name, stock_quantity, purchase_price, sale_price in raw_product_rows:
        _ensure_product_unit_mapping(cur, product_id)
        cur.execute(
            """
            SELECT pu.unit_id,mu.name,pu.conversion_factor,pu.purchase_price,pu.sale_price,
                   pu.is_default_purchase,pu.is_default_sale,pu.is_base_unit
            FROM product_units pu
            JOIN measurement_units mu ON mu.id=pu.unit_id
            WHERE pu.product_id=? AND pu.is_active=1
            ORDER BY pu.is_base_unit DESC, pu.conversion_factor ASC, pu.id ASC
            """,
            (product_id,),
        )
        units = []
        default_unit_id = None
        for row in cur.fetchall():
            unit = {
                "unit_id": row[0],
                "unit_name": row[1],
                "conversion_factor": float(row[2] or 1),
                "purchase_price": float(row[3] or purchase_price or 0),
                "sale_price": float(row[4] or sale_price or 0),
                "is_default_purchase": bool(row[5]),
                "is_default_sale": bool(row[6]),
                "is_base_unit": bool(row[7]),
            }
            if purpose == "sale" and unit["is_default_sale"]:
                default_unit_id = unit["unit_id"]
            if purpose == "purchase" and unit["is_default_purchase"]:
                default_unit_id = unit["unit_id"]
            units.append(unit)
        if units and default_unit_id is None:
            default_unit_id = units[0]["unit_id"]
        product_rows.append(
            (
                product_id,
                name,
                float(sale_price or 0) if purpose == "sale" else float(purchase_price or 0),
                float(stock_quantity or 0),
            )
        )
        data[str(product_id)] = {
            "product_id": product_id,
            "name": name,
            "default_unit_id": default_unit_id,
            "units": units,
        }
    return product_rows, data


def _order_lines_from_form(cur, deps, purpose="sale"):
    parse_positive_amount = deps["parse_positive_amount"]
    default_tax_rate = deps["DEFAULT_TAX_RATE"]
    product_ids = request.form.getlist("product_id[]") or request.form.getlist("product_id")
    unit_ids = request.form.getlist("unit_id[]") or request.form.getlist("unit_id")
    quantities = request.form.getlist("quantity[]") or request.form.getlist("quantity")
    unit_prices = request.form.getlist("unit_price[]") or request.form.getlist("unit_price")
    tax_rates = request.form.getlist("tax_rate[]") or request.form.getlist("tax_rate")
    lines = []
    for idx, product_id in enumerate(product_ids):
        product_id = (product_id or "").strip()
        unit_id = (unit_ids[idx] if idx < len(unit_ids) else "").strip()
        quantity = parse_positive_amount(quantities[idx] if idx < len(quantities) else 0)
        unit_price = parse_positive_amount(unit_prices[idx] if idx < len(unit_prices) else 0)
        tax_rate = parse_positive_amount(tax_rates[idx] if idx < len(tax_rates) else default_tax_rate)
        if not product_id and quantity == 0 and unit_price == 0:
            continue
        cur.execute("SELECT 1 FROM products WHERE id=?", (product_id,))
        if not cur.fetchone() or quantity <= 0 or unit_price <= 0:
            return []
        unit_meta = _resolve_product_unit(cur, int(product_id), unit_id or None, purpose=purpose)
        conversion_factor = float(unit_meta["conversion_factor"] or 1)
        if conversion_factor <= 0:
            return []
        total = quantity * unit_price
        tax_amount = total * tax_rate / 100
        lines.append(
            (
                int(product_id),
                quantity,
                unit_meta["unit_id"],
                unit_meta["unit_name"],
                conversion_factor,
                quantity * conversion_factor,
                unit_price,
                total,
                tax_rate,
                tax_amount,
                total + tax_amount,
            )
        )
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
            lines = _order_lines_from_form(cur, deps, purpose="sale")
            order_date = parse_iso_date(date_value)
            requested_delivery = parse_iso_date(delivery_date)
            if not date_value:
                flash("تاريخ أمر البيع مطلوب.", "danger")
            elif requested_delivery and order_date and requested_delivery < order_date:
                flash("تاريخ التسليم لا يمكن أن يكون أسبق من تاريخ أمر البيع.", "danger")
            elif not lines:
                flash("أضف صنفًا واحدًا على الأقل بكمية وسعر صحيحين.", "danger")
            else:
                total = sum(line[7] for line in lines)
                tax_amount = sum(line[9] for line in lines)
                grand_total = sum(line[10] for line in lines)
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
                        total / quantity if quantity else first_line[6],
                        total,
                        first_line[8],
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
                        """
                        INSERT INTO sales_order_lines(
                            order_id,product_id,quantity,unit_id,unit_name,conversion_factor,quantity_base,
                            unit_price,total,tax_rate,tax_amount,grand_total
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (order_id, *line),
                    )
                log_action(cur, "create", "sales_order", order_id, f"lines={len(lines)}; total={grand_total}")
                conn.commit()
                conn.close()
                flash("تم حفظ أمر البيع متعدد الأصناف.", "success")
                return redirect(url_for("sales_orders"))

        cur.execute("SELECT id,name FROM customers ORDER BY name")
        customers_rows = cur.fetchall()
        product_rows, product_units_map = _build_product_units_map(cur, purpose="sale")
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
                SELECT p.name,sol.quantity,COALESCE(sol.unit_name, p.unit, 'وحدة')
                FROM sales_order_lines sol
                JOIN products p ON p.id=sol.product_id
                WHERE sol.order_id=?
                ORDER BY sol.id
                """,
                (row[0],),
            )
            summary = " / ".join(f"{name} ({qty:g} {unit_name})" for name, qty, unit_name in cur.fetchall())
            rows.append((row[0], row[1], row[2], summary, row[3], row[4], row[5], row[6], row[7]))
        conn.close()
        return render_template(
            "sales_orders.html",
            customers=customers_rows,
            products=product_rows,
            rows=rows,
            product_units_json=json.dumps(product_units_map, ensure_ascii=False),
        )

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
            lines = _order_lines_from_form(cur, deps, purpose="purchase")
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
                total = sum(line[7] for line in lines)
                tax_amount = sum(line[9] for line in lines)
                grand_total = sum(line[10] for line in lines)
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
                        total / quantity if quantity else first_line[6],
                        total,
                        first_line[8],
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
                        """
                        INSERT INTO purchase_order_lines(
                            order_id,product_id,quantity,unit_id,unit_name,conversion_factor,quantity_base,
                            unit_price,total,tax_rate,tax_amount,grand_total
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (order_id, *line),
                    )
                log_action(cur, "create", "purchase_order", order_id, f"lines={len(lines)}; total={grand_total}")
                conn.commit()
                conn.close()
                flash("تم حفظ أمر الشراء متعدد الأصناف.", "success")
                return redirect(url_for("purchase_orders"))

        cur.execute("SELECT id,name FROM suppliers ORDER BY name")
        suppliers_rows = cur.fetchall()
        product_rows, product_units_map = _build_product_units_map(cur, purpose="purchase")
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
                SELECT p.name,pol.quantity,COALESCE(pol.unit_name, p.unit, 'وحدة')
                FROM purchase_order_lines pol
                JOIN products p ON p.id=pol.product_id
                WHERE pol.order_id=?
                ORDER BY pol.id
                """,
                (row[0],),
            )
            summary = " / ".join(f"{name} ({qty:g} {unit_name})" for name, qty, unit_name in cur.fetchall())
            orders.append((row[0], row[1], row[2], summary, row[3], row[4], row[5], row[6], row[7], row[8]))
        conn.close()
        return render_template(
            "purchase_orders.html",
            suppliers=suppliers_rows,
            products=product_rows,
            orders=orders,
            product_units_json=json.dumps(product_units_map, ensure_ascii=False),
        )

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
            SELECT p.name,COALESCE(pol.unit_name,p.unit,'وحدة'),pol.quantity,pol.unit_price,pol.total,pol.tax_amount,pol.grand_total
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
