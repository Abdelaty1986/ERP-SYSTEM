import json
import sqlite3
from urllib.parse import urlencode

from flask import flash, redirect, render_template, request, url_for
from markupsafe import Markup


INBOUND_MOVEMENT_TYPES = {"in", "return_in", "cancel_in"}
OUTBOUND_MOVEMENT_TYPES = {"out", "return_out", "cancel_out"}


def _generate_product_barcode_value(product_id):
    return f"PRD-{int(product_id):08d}"


def _build_product_barcode_payload(product_row):
    supplier_name = product_row[8] if len(product_row) > 8 else ""
    payload = {
        "product_id": product_row[0],
        "barcode": product_row[7] or _generate_product_barcode_value(product_row[0]),
        "code": product_row[1] or "",
        "name": product_row[2],
        "unit": product_row[3],
        "purchase_price": float(product_row[4] or 0),
        "sale_price": float(product_row[5] or 0),
        "supplier": supplier_name or "",
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _build_code39_svg(value):
    patterns = {
        "0": "nnnwwnwnn", "1": "wnnwnnnnw", "2": "nnwwnnnnw", "3": "wnwwnnnnn", "4": "nnnwwnnnw",
        "5": "wnnwwnnnn", "6": "nnwwwnnnn", "7": "nnnwnnwnw", "8": "wnnwnnwnn", "9": "nnwwnnwnn",
        "A": "wnnnnwnnw", "B": "nnwnnwnnw", "C": "wnwnnwnnn", "D": "nnnnwwnnw", "E": "wnnnwwnnn",
        "F": "nnwnwwnnn", "G": "nnnnnwwnw", "H": "wnnnnwwnn", "I": "nnwnnwwnn", "J": "nnnnwwwnn",
        "K": "wnnnnnnww", "L": "nnwnnnnww", "M": "wnwnnnnwn", "N": "nnnnwnnww", "O": "wnnnwnnwn",
        "P": "nnwnwnnwn", "Q": "nnnnnnwww", "R": "wnnnnnwwn", "S": "nnwnnnwwn", "T": "nnnnwnwwn",
        "U": "wwnnnnnnw", "V": "nwwnnnnnw", "W": "wwwnnnnnn", "X": "nwnnwnnnw", "Y": "wwnnwnnnn",
        "Z": "nwwnwnnnn", "-": "nwnnnnwnw", ".": "wwnnnnwnn", " ": "nwwnnnwnn", "$": "nwnwnwnnn",
        "/": "nwnwnnnwn", "+": "nwnnnwnwn", "%": "nnnwnwnwn", "*": "nwnnwnwnn",
    }
    content = f"*{(value or '').upper()}*"
    narrow = 2
    wide = 5
    bar_height = 92
    quiet_zone = 16
    gap = 2
    x = quiet_zone
    rects = []
    for index, char in enumerate(content):
        pattern = patterns.get(char)
        if not pattern:
            continue
        for pos, token in enumerate(pattern):
            width = wide if token == "w" else narrow
            if pos % 2 == 0:
                rects.append(f'<rect x="{x}" y="0" width="{width}" height="{bar_height}" rx="0.6" ry="0.6"></rect>')
            x += width
            if pos != len(pattern) - 1:
                x += gap
        if index != len(content) - 1:
            x += narrow * 3
    total_width = x + quiet_zone
    return Markup(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_width} {bar_height}" role="img" aria-label="Barcode {value}">'
        f'<rect width="{total_width}" height="{bar_height}" fill="#ffffff"></rect><g fill="#111827">{"".join(rects)}</g></svg>'
    )


def _ensure_product_barcode(cur, product_id):
    cur.execute(
        """
        SELECT p.id,p.code,p.name,p.unit,p.purchase_price,p.sale_price,p.stock_quantity,
               p.barcode_value,COALESCE(s.name,'')
        FROM products p
        LEFT JOIN suppliers s ON s.id = p.default_supplier_id
        WHERE p.id=?
        """,
        (product_id,),
    )
    product = cur.fetchone()
    if not product:
        return None
    barcode_value = product[7] or _generate_product_barcode_value(product[0])
    barcode_payload = _build_product_barcode_payload(product)
    cur.execute("UPDATE products SET barcode_value=?, barcode_payload=? WHERE id=?", (barcode_value, barcode_payload, product_id))
    return barcode_value, barcode_payload


def _fetch_categories(cur, active_only=False):
    sql = "SELECT id,name,parent_id,status,created_at FROM product_categories"
    params = []
    if active_only:
        sql += " WHERE status='active'"
    sql += " ORDER BY COALESCE(parent_id,id), parent_id IS NOT NULL, name"
    cur.execute(sql, params)
    return cur.fetchall()


def _category_children(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault(row[2], []).append(row)
    return grouped


def _flatten_categories(rows, active_only=False):
    children = _category_children(rows)
    flattened = []

    def walk(parent_id=None, depth=0, parent_label=""):
        for row in children.get(parent_id, []):
            if active_only and row[3] != "active":
                continue
            full_label = f"{parent_label} / {row[1]}" if parent_label else row[1]
            option_label = f"{'-- ' * depth}{row[1]}"
            flattened.append(
                {
                    "id": row[0],
                    "name": row[1],
                    "parent_id": row[2],
                    "status": row[3],
                    "created_at": row[4],
                    "depth": depth,
                    "option_label": option_label,
                    "full_label": full_label,
                }
            )
            walk(row[0], depth + 1, full_label)

    walk()
    return flattened


def build_product_categories_view(deps):
    db = deps["db"]
    log_action = deps["log_action"]

    def product_categories():
        conn = db()
        cur = conn.cursor()
        edit_id = request.args.get("edit_id", "").strip()
        if request.method == "POST":
            action = request.form.get("action", "save").strip()
            if action == "toggle":
                category_id = request.form.get("category_id")
                cur.execute("SELECT id,name,status FROM product_categories WHERE id=?", (category_id,))
                row = cur.fetchone()
                if row:
                    new_status = "inactive" if row[2] == "active" else "active"
                    cur.execute("UPDATE product_categories SET status=? WHERE id=?", (new_status, category_id))
                    log_action(cur, "update", "product_category", category_id, f"status={new_status}")
                    conn.commit()
                    flash("تم تحديث حالة التصنيف.", "success")
                conn.close()
                return redirect(url_for("product_categories"))

            category_id = request.form.get("category_id") or None
            name = (request.form.get("name") or "").strip()
            parent_id = request.form.get("parent_id") or None
            if parent_id == "":
                parent_id = None
            if category_id and parent_id and str(category_id) == str(parent_id):
                flash("لا يمكن ربط التصنيف بنفسه كأب.", "danger")
            elif not name:
                flash("اسم التصنيف مطلوب.", "danger")
            else:
                if category_id:
                    cur.execute("UPDATE product_categories SET name=?, parent_id=? WHERE id=?", (name, parent_id, category_id))
                    log_action(cur, "update", "product_category", category_id, name)
                    flash("تم تعديل التصنيف.", "success")
                else:
                    cur.execute("INSERT INTO product_categories(name,parent_id) VALUES (?,?)", (name, parent_id))
                    new_id = cur.lastrowid
                    log_action(cur, "create", "product_category", new_id, name)
                    flash("تمت إضافة التصنيف.", "success")
                conn.commit()
                conn.close()
                return redirect(url_for("product_categories"))

        rows = _fetch_categories(cur)
        categories = _flatten_categories(rows)
        edit_category = None
        if edit_id.isdigit():
            cur.execute("SELECT id,name,parent_id,status,created_at FROM product_categories WHERE id=?", (int(edit_id),))
            edit_category = cur.fetchone()
        conn.close()
        return render_template("product_categories.html", categories=categories, edit_category=edit_category)

    return product_categories


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
            category_id = request.form.get("category_id") or None
            try:
                purchase_price = float(request.form.get("purchase_price", 0) or 0)
                sale_price = float(request.form.get("sale_price", 0) or 0)
            except ValueError:
                purchase_price = 0
                sale_price = 0
                flash("أسعار الصنف يجب أن تكون أرقامًا صحيحة.", "danger")
                supplier_id = None
            if supplier_id:
                cur.execute("SELECT 1 FROM suppliers WHERE id=?", (supplier_id,))
                if not cur.fetchone():
                    supplier_id = None
            if category_id:
                cur.execute("SELECT 1 FROM product_categories WHERE id=?", (category_id,))
                if not cur.fetchone():
                    category_id = None
            if not name:
                flash("اسم الصنف مطلوب.", "danger")
            elif purchase_price < 0 or sale_price < 0:
                flash("الأسعار لا يمكن أن تكون سالبة.", "danger")
            else:
                try:
                    cur.execute(
                        """
                        INSERT INTO products(code,name,unit,purchase_price,sale_price,default_supplier_id,category_id)
                        VALUES (?,?,?,?,?,?,?)
                        """,
                        (code or None, name, unit, purchase_price, sale_price, supplier_id, category_id),
                    )
                    product_id = cur.lastrowid
                    _ensure_product_barcode(cur, product_id)
                    conn.commit()
                    conn.close()
                    flash("تمت إضافة الصنف وتوليد الباركود الخاص به تلقائيًا.", "success")
                    return redirect(url_for("products"))
                except sqlite3.IntegrityError:
                    flash("كود الصنف مستخدم بالفعل.", "danger")

        filters = {
            "q": (request.args.get("q") or "").strip(),
            "supplier_id": (request.args.get("supplier_id") or "").strip(),
            "category_id": (request.args.get("category_id") or "").strip(),
        }
        cur.execute("SELECT id,name FROM suppliers ORDER BY name")
        suppliers_rows = cur.fetchall()
        category_rows = _fetch_categories(cur, active_only=True)
        category_options = _flatten_categories(category_rows, active_only=True)
        where = []
        params = []
        if filters["q"]:
            where.append("(p.code LIKE ? OR p.name LIKE ? OR p.barcode_value LIKE ?)")
            params.extend([f"%{filters['q']}%", f"%{filters['q']}%", f"%{filters['q']}%"])
        if filters["supplier_id"].isdigit():
            where.append("p.default_supplier_id = ?")
            params.append(int(filters["supplier_id"]))
        if filters["category_id"].isdigit():
            where.append("p.category_id = ?")
            params.append(int(filters["category_id"]))
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        cur.execute(
            """
            SELECT p.id,p.code,p.name,p.unit,p.purchase_price,p.sale_price,p.stock_quantity,
                   p.barcode_value,p.barcode_payload,COALESCE(s.name,''),p.category_id,
                   COALESCE(pc.name,''),COALESCE(parent.name,'')
            FROM products p
            LEFT JOIN suppliers s ON s.id=p.default_supplier_id
            LEFT JOIN product_categories pc ON pc.id=p.category_id
            LEFT JOIN product_categories parent ON parent.id=pc.parent_id
            """
            + (f"\n{where_sql}" if where_sql else "")
            + "\nORDER BY p.id DESC",
            params,
        )
        rows = cur.fetchall()
        for row in rows:
            if not row[7] or not row[8]:
                _ensure_product_barcode(cur, row[0])
        conn.commit()
        cur.execute(
            """
            SELECT p.id,p.code,p.name,p.unit,p.purchase_price,p.sale_price,p.stock_quantity,
                   p.barcode_value,p.barcode_payload,COALESCE(s.name,''),p.category_id,
                   COALESCE(pc.name,''),COALESCE(parent.name,'')
            FROM products p
            LEFT JOIN suppliers s ON s.id=p.default_supplier_id
            LEFT JOIN product_categories pc ON pc.id=p.category_id
            LEFT JOIN product_categories parent ON parent.id=pc.parent_id
            """
            + (f"\n{where_sql}" if where_sql else "")
            + "\nORDER BY p.id DESC",
            params,
        )
        rows = cur.fetchall()
        conn.close()
        return render_template(
            "products.html",
            products=rows,
            suppliers=suppliers_rows,
            filters=filters,
            categories=category_options,
        )

    return products


def build_product_barcode_view(deps):
    db = deps["db"]

    def product_barcode(id):
        conn = db()
        cur = conn.cursor()
        barcode_result = _ensure_product_barcode(cur, id)
        if not barcode_result:
            conn.close()
            flash("الصنف غير موجود.", "danger")
            return redirect(url_for("products"))
        conn.commit()
        cur.execute(
            """
            SELECT p.id,p.code,p.name,p.unit,p.purchase_price,p.sale_price,p.stock_quantity,
                   p.barcode_value,p.barcode_payload,COALESCE(s.name,'')
            FROM products p
            LEFT JOIN suppliers s ON s.id=p.default_supplier_id
            WHERE p.id=?
            """,
            (id,),
        )
        product = cur.fetchone()
        conn.close()
        payload = json.loads(product[8]) if product[8] else {}
        barcode_svg = _build_code39_svg(product[7])
        return render_template("product_barcode.html", product=product, payload=payload, barcode_svg=barcode_svg)

    return product_barcode


def build_edit_product_view(deps):
    db = deps["db"]
    log_action = deps["log_action"]
    parse_positive_amount = deps["parse_positive_amount"]

    def edit_product(id):
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id,code,name,unit,purchase_price,sale_price,default_supplier_id,category_id
            FROM products
            WHERE id=?
            """,
            (id,),
        )
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
            category_id = request.form.get("category_id") or None
            purchase_price = parse_positive_amount(request.form.get("purchase_price"))
            sale_price = parse_positive_amount(request.form.get("sale_price"))
            if supplier_id:
                cur.execute("SELECT 1 FROM suppliers WHERE id=?", (supplier_id,))
                if not cur.fetchone():
                    supplier_id = None
            if category_id:
                cur.execute("SELECT 1 FROM product_categories WHERE id=?", (category_id,))
                if not cur.fetchone():
                    category_id = None
            if not name:
                flash("اسم الصنف مطلوب.", "danger")
            else:
                try:
                    cur.execute(
                        """
                        UPDATE products
                        SET code=?,name=?,unit=?,purchase_price=?,sale_price=?,default_supplier_id=?,category_id=?
                        WHERE id=?
                        """,
                        (code or None, name, unit, purchase_price, sale_price, supplier_id, category_id, id),
                    )
                    _ensure_product_barcode(cur, id)
                    log_action(cur, "update", "product", id, name)
                    conn.commit()
                    conn.close()
                    flash("تم تعديل الصنف وتحديث بيانات الباركود.", "success")
                    return redirect(url_for("products"))
                except sqlite3.IntegrityError:
                    flash("كود الصنف مستخدم بالفعل.", "danger")
        cur.execute("SELECT id,name FROM suppliers ORDER BY name")
        suppliers_rows = cur.fetchall()
        category_options = _flatten_categories(_fetch_categories(cur, active_only=True), active_only=True)
        conn.close()
        return render_template("edit_product.html", product=product, suppliers=suppliers_rows, categories=category_options)

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
        filters = {
            "q": (request.args.get("q") or "").strip(),
            "movement_type": (request.args.get("movement_type") or "").strip(),
            "date_from": (request.args.get("date_from") or "").strip(),
            "date_to": (request.args.get("date_to") or "").strip(),
            "category_id": (request.args.get("category_id") or "").strip(),
        }
        where = []
        params = []
        if filters["q"]:
            where.append("(p.name LIKE ? OR p.code LIKE ? OR p.barcode_value LIKE ?)")
            params.extend([f"%{filters['q']}%", f"%{filters['q']}%", f"%{filters['q']}%"])
        if filters["movement_type"] in {"in", "out"}:
            allowed_types = sorted(INBOUND_MOVEMENT_TYPES if filters["movement_type"] == "in" else OUTBOUND_MOVEMENT_TYPES)
            placeholders = ",".join(["?"] * len(allowed_types))
            where.append(f"m.movement_type IN ({placeholders})")
            params.extend(allowed_types)
        if filters["date_from"]:
            where.append("m.date >= ?")
            params.append(filters["date_from"])
        if filters["date_to"]:
            where.append("m.date <= ?")
            params.append(filters["date_to"])
        if filters["category_id"].isdigit():
            where.append("p.category_id = ?")
            params.append(int(filters["category_id"]))
        cur.execute(
            """
            SELECT m.date,p.name,m.movement_type,m.quantity,m.reference_type,m.reference_id,m.notes,
                   COALESCE(parent.name || ' / ', '') || COALESCE(pc.name,''),
                   CASE
                       WHEN m.movement_type='in' THEN 'دخول'
                       WHEN m.movement_type='out' THEN 'خروج'
                       WHEN m.movement_type='return_in' THEN 'مرتجع دخول'
                       WHEN m.movement_type='return_out' THEN 'مرتجع خروج'
                       WHEN m.movement_type='cancel_in' THEN 'إلغاء بخروج عكسي'
                       WHEN m.movement_type='cancel_out' THEN 'إلغاء بدخول عكسي'
                       ELSE m.movement_type
                   END
            FROM inventory_movements m
            JOIN products p ON m.product_id=p.id
            LEFT JOIN product_categories pc ON pc.id=p.category_id
            LEFT JOIN product_categories parent ON parent.id=pc.parent_id
            """
            + ("\n WHERE " + " AND ".join(where) if where else "")
            + "\n ORDER BY m.id DESC",
            params,
        )
        rows = cur.fetchall()
        categories = _flatten_categories(_fetch_categories(cur, active_only=True), active_only=True)
        conn.close()
        return render_template("inventory.html", rows=rows, filters=filters, categories=categories)

    return inventory


def build_inventory_report_view(deps):
    db = deps["db"]
    excel_response = deps["excel_response"]

    def inventory_report():
        conn = db()
        cur = conn.cursor()
        filters = {
            "q": (request.args.get("q") or "").strip(),
            "stock_filter": (request.args.get("stock_filter") or "").strip(),
            "category_id": (request.args.get("category_id") or "").strip(),
        }
        where = []
        params = []
        if filters["q"]:
            where.append("(p.code LIKE ? OR p.name LIKE ? OR p.barcode_value LIKE ?)")
            params.extend([f"%{filters['q']}%", f"%{filters['q']}%", f"%{filters['q']}%"])
        if filters["stock_filter"] == "low":
            where.append("p.stock_quantity <= 5")
        elif filters["stock_filter"] == "available":
            where.append("p.stock_quantity > 0")
        elif filters["stock_filter"] == "zero":
            where.append("p.stock_quantity = 0")
        if filters["category_id"].isdigit():
            where.append("p.category_id = ?")
            params.append(int(filters["category_id"]))
        cur.execute(
            """
            SELECT p.code,p.name,p.unit,p.stock_quantity,p.purchase_price,p.sale_price,
                   p.stock_quantity * p.purchase_price AS stock_value,
                   COALESCE(parent.name || ' / ', '') || COALESCE(pc.name,'')
            FROM products p
            LEFT JOIN product_categories pc ON pc.id=p.category_id
            LEFT JOIN product_categories parent ON parent.id=pc.parent_id
            """
            + ("\n WHERE " + " AND ".join(where) if where else "")
            + "\n ORDER BY p.name",
            params,
        )
        rows = cur.fetchall()
        total_value = sum(row[6] for row in rows)
        low_stock = [row for row in rows if row[3] <= 5]
        categories = _flatten_categories(_fetch_categories(cur, active_only=True), active_only=True)
        if request.args.get("format") == "excel":
            conn.close()
            return excel_response(
                "inventory-report.xls",
                ["الكود", "الصنف", "الوحدة", "الرصيد", "سعر الشراء", "سعر البيع", "قيمة المخزون", "التصنيف"],
                rows,
                title="تقرير المخزون",
            )
        conn.close()
        export_query = urlencode({k: v for k, v in filters.items() if v})
        return render_template(
            "inventory_report.html",
            rows=rows,
            total_value=total_value,
            low_stock=low_stock,
            filters=filters,
            export_query=export_query,
            categories=categories,
        )

    return inventory_report
