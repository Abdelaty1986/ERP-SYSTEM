import sqlite3

from flask import flash, redirect, render_template, request, url_for


def build_products_view(deps):
    db = deps["db"]

    def products():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            code = request.form.get("code", "").strip()
            name = request.form.get("name", "").strip()
            unit = request.form.get("unit", "وحدة").strip() or "وحدة"
            supplier_id = request.form.get("default_supplier_id") or None
            try:
                purchase_price = float(request.form.get("purchase_price", 0) or 0)
                sale_price = float(request.form.get("sale_price", 0) or 0)
            except ValueError:
                purchase_price = 0
                sale_price = 0
                flash("أسعار المنتج يجب أن تكون أرقامًا.", "danger")
                supplier_id = None
            if supplier_id:
                cur.execute("SELECT 1 FROM suppliers WHERE id=?", (supplier_id,))
                if not cur.fetchone():
                    supplier_id = None
            if not name:
                flash("اسم المنتج مطلوب.", "danger")
            elif purchase_price < 0 or sale_price < 0:
                flash("الأسعار لا يمكن أن تكون سالبة.", "danger")
            else:
                try:
                    cur.execute(
                        "INSERT INTO products(code,name,unit,purchase_price,sale_price,default_supplier_id) VALUES (?,?,?,?,?,?)",
                        (code or None, name, unit, purchase_price, sale_price, supplier_id),
                    )
                    conn.commit()
                    conn.close()
                    flash("تمت إضافة الصنف.", "success")
                    return redirect(url_for("products"))
                except sqlite3.IntegrityError:
                    flash("كود الصنف مستخدم بالفعل.", "danger")
        cur.execute("SELECT id,name FROM suppliers ORDER BY name")
        suppliers_rows = cur.fetchall()
        cur.execute(
            """
            SELECT p.id,p.code,p.name,p.unit,p.purchase_price,p.sale_price,p.stock_quantity,COALESCE(s.name,'')
            FROM products p
            LEFT JOIN suppliers s ON s.id=p.default_supplier_id
            ORDER BY p.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("products.html", products=rows, suppliers=suppliers_rows)

    return products


def build_edit_product_view(deps):
    db = deps["db"]
    log_action = deps["log_action"]
    parse_positive_amount = deps["parse_positive_amount"]

    def edit_product(id):
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT id,code,name,unit,purchase_price,sale_price,default_supplier_id FROM products WHERE id=?", (id,))
        product = cur.fetchone()
        if not product:
            conn.close()
            flash("الصنف غير موجود.", "danger")
            return redirect(url_for("products"))
        if request.method == "POST":
            code = request.form.get("code", "").strip()
            name = request.form.get("name", "").strip()
            unit = request.form.get("unit", "وحدة").strip() or "وحدة"
            supplier_id = request.form.get("default_supplier_id") or None
            purchase_price = parse_positive_amount(request.form.get("purchase_price"))
            sale_price = parse_positive_amount(request.form.get("sale_price"))
            if supplier_id:
                cur.execute("SELECT 1 FROM suppliers WHERE id=?", (supplier_id,))
                if not cur.fetchone():
                    supplier_id = None
            if not name:
                flash("اسم الصنف مطلوب.", "danger")
            else:
                try:
                    cur.execute(
                        "UPDATE products SET code=?,name=?,unit=?,purchase_price=?,sale_price=?,default_supplier_id=? WHERE id=?",
                        (code or None, name, unit, purchase_price, sale_price, supplier_id, id),
                    )
                    log_action(cur, "update", "product", id, name)
                    conn.commit()
                    conn.close()
                    flash("تم تعديل الصنف.", "success")
                    return redirect(url_for("products"))
                except sqlite3.IntegrityError:
                    flash("كود الصنف مستخدم بالفعل.", "danger")
        cur.execute("SELECT id,name FROM suppliers ORDER BY name")
        suppliers_rows = cur.fetchall()
        conn.close()
        return render_template("edit_product.html", product=product, suppliers=suppliers_rows)

    return edit_product


def build_delete_product_view(deps):
    db = deps["db"]
    log_action = deps["log_action"]

    def delete_product(id):
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT name FROM products WHERE id=?", (id,))
        product = cur.fetchone()
        if not product:
            conn.close()
            flash("الصنف غير موجود.", "danger")
            return redirect(url_for("products"))
        for table, column in [
            ("sales_invoices", "product_id"),
            ("purchase_invoices", "product_id"),
            ("sales_invoice_lines", "product_id"),
            ("purchase_invoice_lines", "product_id"),
            ("sales_returns", "product_id"),
            ("purchase_returns", "product_id"),
            ("inventory_movements", "product_id"),
            ("sales_orders", "product_id"),
            ("purchase_orders", "product_id"),
            ("sales_order_lines", "product_id"),
            ("purchase_order_lines", "product_id"),
            ("sales_delivery_notes", "product_id"),
            ("purchase_receipts", "product_id"),
        ]:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {column}=?", (id,))
            if cur.fetchone()[0]:
                conn.close()
                flash("لا يمكن حذف الصنف لوجود حركات مرتبطة به.", "danger")
                return redirect(url_for("products"))
        cur.execute("DELETE FROM products WHERE id=?", (id,))
        log_action(cur, "delete", "product", id, product[0])
        conn.commit()
        conn.close()
        flash("تم حذف الصنف.", "success")
        return redirect(url_for("products"))

    return delete_product


def build_inventory_view(deps):
    db = deps["db"]

    def inventory():
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT m.date,p.name,m.movement_type,m.quantity,m.reference_type,m.reference_id,m.notes
            FROM inventory_movements m
            JOIN products p ON m.product_id=p.id
            ORDER BY m.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("inventory.html", rows=rows)

    return inventory


def build_inventory_report_view(deps):
    db = deps["db"]
    excel_response = deps["excel_response"]

    def inventory_report():
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT code,name,unit,stock_quantity,purchase_price,sale_price,
                   stock_quantity * purchase_price AS stock_value
            FROM products
            ORDER BY name
            """
        )
        rows = cur.fetchall()
        total_value = sum(row[6] for row in rows)
        low_stock = [row for row in rows if row[3] <= 5]
        if request.args.get("format") == "excel":
            conn.close()
            return excel_response(
                "inventory-report.xls",
                ["الكود", "الصنف", "الوحدة", "الرصيد", "سعر الشراء", "سعر البيع", "قيمة المخزون"],
                rows,
                title="تقرير المخزون",
            )
        conn.close()
        return render_template(
            "inventory_report.html",
            rows=rows,
            total_value=total_value,
            low_stock=low_stock,
        )

    return inventory_report
