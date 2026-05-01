import json

from flask import flash, redirect, render_template, request, url_for
from modules.accounting.ledger_engine import post_simple_entry


def _invoice_product_options(cur, invoice_type, invoice_id):
    if invoice_type == "sales":
        cur.execute(
            """
            SELECT sil.product_id,p.name,sil.quantity,sil.unit_price,
                   COALESCE((SELECT SUM(quantity) FROM sales_returns sr WHERE sr.sales_invoice_id=sil.invoice_id AND sr.product_id=sil.product_id),0)
            FROM sales_invoice_lines sil
            JOIN products p ON p.id=sil.product_id
            WHERE sil.invoice_id=?
            ORDER BY sil.id
            """,
            (invoice_id,),
        )
        rows = cur.fetchall()
        if not rows:
            cur.execute(
                """
                SELECT s.product_id,p.name,s.quantity,s.unit_price,
                       COALESCE((SELECT SUM(quantity) FROM sales_returns sr WHERE sr.sales_invoice_id=s.id AND sr.product_id=s.product_id),0)
                FROM sales_invoices s
                JOIN products p ON p.id=s.product_id
                WHERE s.id=?
                """,
                (invoice_id,),
            )
            rows = cur.fetchall()
    else:
        cur.execute(
            """
            SELECT pil.product_id,p.name,pil.quantity,pil.unit_price,
                   COALESCE((SELECT SUM(quantity) FROM purchase_returns pr WHERE pr.purchase_invoice_id=pil.invoice_id AND pr.product_id=pil.product_id),0)
            FROM purchase_invoice_lines pil
            JOIN products p ON p.id=pil.product_id
            WHERE pil.invoice_id=?
            ORDER BY pil.id
            """,
            (invoice_id,),
        )
        rows = cur.fetchall()
        if not rows:
            cur.execute(
                """
                SELECT p.product_id,pr.name,p.quantity,p.unit_price,
                       COALESCE((SELECT SUM(quantity) FROM purchase_returns pr2 WHERE pr2.purchase_invoice_id=p.id AND pr2.product_id=p.product_id),0)
                FROM purchase_invoices p
                JOIN products pr ON pr.id=p.product_id
                WHERE p.id=?
                """,
                (invoice_id,),
            )
            rows = cur.fetchall()
    result = []
    for product_id, name, quantity, unit_price, returned_qty in rows:
        available = max((quantity or 0) - (returned_qty or 0), 0)
        result.append(
            {
                "product_id": product_id,
                "name": name,
                "quantity": quantity or 0,
                "unit_price": unit_price or 0,
                "available": available,
            }
        )
    return result


def build_sales_returns_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]
    default_tax_rate = deps["DEFAULT_TAX_RATE"]

    def sales_returns():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            invoice_id = int(parse_positive_amount(request.form.get("sales_invoice_id")) or 0)
            product_ids = request.form.getlist("product_id[]") or request.form.getlist("product_id")
            quantities = request.form.getlist("quantity[]") or request.form.getlist("quantity")
            po_ref = request.form.get("po_ref", "").strip()
            gr_ref = request.form.get("gr_ref", "").strip()
            notes = request.form.get("notes", "").strip()
            cur.execute("SELECT customer_id,payment_type,tax_rate FROM sales_invoices WHERE id=?", (invoice_id,))
            invoice = cur.fetchone()
            options_list = _invoice_product_options(cur, "sales", invoice_id)
            options = {item["product_id"]: item for item in options_list}
            lines = []
            for idx, product_id in enumerate(product_ids):
                product_id = int(parse_positive_amount(product_id) or 0)
                quantity = parse_positive_amount(quantities[idx] if idx < len(quantities) else 0)
                option = options.get(product_id)
                if product_id and quantity > 0 and option:
                    lines.append((product_id, quantity, option))
            if not date_value or not invoice or not lines:
                flash("راجع بيانات مردود البيع.", "danger")
            elif any(line[1] > line[2]["available"] for line in lines):
                flash("يوجد صنف تتجاوز كميته الكمية المتاحة للمردود.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("sales_returns"))
                credit_code = "1300" if invoice[1] == "credit" else "1100"
                for product_id, quantity, option in lines:
                    total = quantity * option["unit_price"]
                    tax_amount = total * (invoice[2] or default_tax_rate) / 100
                    grand_total = total + tax_amount
                    cur.execute("SELECT name,purchase_price FROM products WHERE id=?", (product_id,))
                    product = cur.fetchone()
                    cost_total = quantity * (product[1] or 0)
                    journal_id = post_simple_entry(
                        cur=cur,
                        date=date_value,
                        description=f"مردود بيع - {product[0]}",
                        debit_code="4200",
                        credit_code=credit_code,
                        amount=total,
                    )
                    tax_journal_id = post_simple_entry(
                        cur=cur,
                        date=date_value,
                        description=f"ضريبة مردود بيع - {product[0]}",
                        debit_code="2200",
                        credit_code=credit_code,
                        amount=tax_amount,
                    ) if tax_amount > 0 else None
                    cogs_journal_id = post_simple_entry(
                        cur=cur,
                        date=date_value,
                        description=f"عكس تكلفة مردود بيع - {product[0]}",
                        debit_code="1400",
                        credit_code="6100",
                        amount=cost_total,
                    ) if cost_total > 0 else None
                    cur.execute(
                        """
                        INSERT INTO sales_returns(date,sales_invoice_id,product_id,quantity,unit_price,total,tax_amount,grand_total,cost_total,journal_id,tax_journal_id,cogs_journal_id,po_ref,gr_ref,notes)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (date_value, invoice_id, product_id, quantity, option["unit_price"], total, tax_amount, grand_total, cost_total, journal_id, tax_journal_id, cogs_journal_id, po_ref, gr_ref, notes),
                    )
                    return_id = cur.lastrowid
                    mark_journal_source(cur, "sales_return", return_id, journal_id, tax_journal_id, cogs_journal_id)
                    cur.execute("UPDATE products SET stock_quantity=stock_quantity+? WHERE id=?", (quantity, product_id))
                    cur.execute(
                        "INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes) VALUES (?,?,?,?,?,?,?)",
                        (date_value, product_id, "return_in", quantity, "sales_return", return_id, notes or "مردود بيع"),
                    )
                    log_action(cur, "create", "sales_return", return_id, f"invoice={invoice_id}; total={grand_total}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash("تم تسجيل مردودات المبيعات.", "success")
                return redirect(url_for("sales_returns"))
        cur.execute("SELECT id,date,grand_total FROM sales_invoices WHERE status='posted' ORDER BY id DESC")
        invoices = cur.fetchall()
        invoice_products = {}
        for row in invoices:
            invoice_products[row[0]] = _invoice_product_options(cur, "sales", row[0])
        cur.execute(
            """
            SELECT r.id,r.date,COALESCE(s.id,''),p.name,r.quantity,r.grand_total,r.status
            FROM sales_returns r
            LEFT JOIN sales_invoices s ON s.id=r.sales_invoice_id
            JOIN products p ON p.id=r.product_id
            ORDER BY r.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("returns.html", title="مردودات المبيعات", rows=rows, invoices=invoices, invoice_products_json=json.dumps(invoice_products, ensure_ascii=False), action_url=url_for("sales_returns"), invoice_field="sales_invoice_id")

    return sales_returns


def build_purchase_returns_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]
    default_tax_rate = deps["DEFAULT_TAX_RATE"]

    def purchase_returns():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            invoice_id = int(parse_positive_amount(request.form.get("purchase_invoice_id")) or 0)
            product_ids = request.form.getlist("product_id[]") or request.form.getlist("product_id")
            quantities = request.form.getlist("quantity[]") or request.form.getlist("quantity")
            po_ref = request.form.get("po_ref", "").strip()
            gr_ref = request.form.get("gr_ref", "").strip()
            notes = request.form.get("notes", "").strip()
            cur.execute("SELECT supplier_id,payment_type,tax_rate FROM purchase_invoices WHERE id=?", (invoice_id,))
            invoice = cur.fetchone()
            options_list = _invoice_product_options(cur, "purchase", invoice_id)
            options = {item["product_id"]: item for item in options_list}
            lines = []
            for idx, product_id in enumerate(product_ids):
                product_id = int(parse_positive_amount(product_id) or 0)
                quantity = parse_positive_amount(quantities[idx] if idx < len(quantities) else 0)
                option = options.get(product_id)
                if product_id and quantity > 0 and option:
                    lines.append((product_id, quantity, option))
            if not date_value or not invoice or not lines:
                flash("راجع بيانات مردود المورد.", "danger")
            else:
                for product_id, quantity, option in lines:
                    cur.execute("SELECT stock_quantity,name,purchase_price FROM products WHERE id=?", (product_id,))
                    product = cur.fetchone()
                    if not product or product[0] < quantity or quantity > option["available"]:
                        conn.close()
                        flash("راجع الكميات المتاحة للمردود أو رصيد المخزون.", "danger")
                        return redirect(url_for("purchase_returns"))
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("purchase_returns"))
                debit_code = "2100" if invoice[1] == "credit" else "1100"
                for product_id, quantity, option in lines:
                    cur.execute("SELECT name,purchase_price FROM products WHERE id=?", (product_id,))
                    product = cur.fetchone()
                    total = quantity * option["unit_price"]
                    tax_amount = total * (invoice[2] or default_tax_rate) / 100
                    grand_total = total + tax_amount
                    journal_id = create_auto_journal(cur, date_value, f"مردود مشتريات - {product[0]}", debit_code, "1400", total)
                    tax_journal_id = create_auto_journal(cur, date_value, f"ضريبة مردود مشتريات - {product[0]}", debit_code, "1500", tax_amount) if tax_amount > 0 else None
                    cur.execute(
                        """
                        INSERT INTO purchase_returns(date,purchase_invoice_id,supplier_id,product_id,quantity,unit_price,total,tax_amount,grand_total,journal_id,tax_journal_id,po_ref,gr_ref,notes)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (date_value, invoice_id, invoice[0], product_id, quantity, option["unit_price"], total, tax_amount, grand_total, journal_id, tax_journal_id, po_ref, gr_ref, notes),
                    )
                    return_id = cur.lastrowid
                    mark_journal_source(cur, "purchase_return", return_id, journal_id, tax_journal_id)
                    cur.execute("UPDATE products SET stock_quantity=stock_quantity-? WHERE id=?", (quantity, product_id))
                    cur.execute(
                        "INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes) VALUES (?,?,?,?,?,?,?)",
                        (date_value, product_id, "return_out", -quantity, "purchase_return", return_id, notes or "مردود مشتريات"),
                    )
                    log_action(cur, "create", "purchase_return", return_id, f"invoice={invoice_id}; total={grand_total}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash("تم تسجيل مردودات الموردين.", "success")
                return redirect(url_for("purchase_returns"))
        cur.execute("SELECT id,date,grand_total FROM purchase_invoices WHERE status='posted' ORDER BY id DESC")
        invoices = cur.fetchall()
        invoice_products = {}
        for row in invoices:
            invoice_products[row[0]] = _invoice_product_options(cur, "purchase", row[0])
        cur.execute(
            """
            SELECT r.id,r.date,COALESCE(pu.id,''),p.name,r.quantity,r.grand_total,r.status
            FROM purchase_returns r
            LEFT JOIN purchase_invoices pu ON pu.id=r.purchase_invoice_id
            JOIN products p ON p.id=r.product_id
            ORDER BY r.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("returns.html", title="مردودات الموردين", rows=rows, invoices=invoices, invoice_products_json=json.dumps(invoice_products, ensure_ascii=False), action_url=url_for("purchase_returns"), invoice_field="purchase_invoice_id")

    return purchase_returns


def build_sales_credit_notes_view(deps):
    db = deps["db"]
    ensure_open_period = deps["ensure_open_period"]
    next_document_number = deps["next_document_number"]
    log_action = deps["log_action"]
    parse_positive_amount = deps["parse_positive_amount"]

    def sales_credit_notes():
        conn = db()
        cur = conn.cursor()

        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            sales_return_id = int(parse_positive_amount(request.form.get("sales_return_id")) or 0)
            notes = request.form.get("notes", "").strip()
            cur.execute(
                """
                SELECT sr.id,sr.sales_invoice_id,si.customer_id,sr.product_id,sr.quantity,sr.unit_price,sr.total,sr.tax_amount,sr.grand_total
                FROM sales_returns sr
                JOIN sales_invoices si ON si.id=sr.sales_invoice_id
                WHERE sr.id=?
                """,
                (sales_return_id,),
            )
            sales_return = cur.fetchone()
            cur.execute("SELECT 1 FROM sales_credit_notes WHERE sales_return_id=?", (sales_return_id,))
            existing = cur.fetchone()
            if not date_value:
                flash("تاريخ إشعار التسوية الدائن مطلوب.", "danger")
            elif not sales_return:
                flash("مردود المبيعات المحدد غير موجود.", "danger")
            elif existing:
                flash("تم إصدار إشعار تسوية دائن لهذا المردود من قبل.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("sales_credit_notes"))
                doc_no = next_document_number(cur, "sales_credit_notes")
                cur.execute(
                    """
                    INSERT INTO sales_credit_notes(
                        date,doc_no,sales_return_id,sales_invoice_id,customer_id,product_id,quantity,unit_price,total,tax_amount,grand_total,notes,status
                    )
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        date_value,
                        doc_no,
                        sales_return[0],
                        sales_return[1],
                        sales_return[2],
                        sales_return[3],
                        sales_return[4],
                        sales_return[5],
                        sales_return[6],
                        sales_return[7],
                        sales_return[8],
                        notes,
                        "posted",
                    ),
                )
                note_id = cur.lastrowid
                log_action(cur, "create", "sales_credit_note", note_id, f"{doc_no}; return_id={sales_return_id}")
                conn.commit()
                conn.close()
                flash(f"تم إنشاء إشعار التسوية الدائن {doc_no}.", "success")
                return redirect(url_for("sales_credit_notes"))

        cur.execute(
            """
            SELECT sr.id,sr.date,c.name,p.name,sr.grand_total
            FROM sales_returns sr
            JOIN sales_invoices si ON si.id=sr.sales_invoice_id
            LEFT JOIN customers c ON c.id=si.customer_id
            JOIN products p ON p.id=sr.product_id
            LEFT JOIN sales_credit_notes scn ON scn.sales_return_id=sr.id
            WHERE scn.id IS NULL
            ORDER BY sr.id DESC
            """
        )
        open_returns = cur.fetchall()
        cur.execute(
            """
            SELECT scn.id,scn.date,scn.doc_no,COALESCE(c.name,'عميل نقدي'),p.name,scn.quantity,scn.grand_total,scn.sales_return_id
            FROM sales_credit_notes scn
            LEFT JOIN customers c ON c.id=scn.customer_id
            LEFT JOIN products p ON p.id=scn.product_id
            ORDER BY scn.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("sales_credit_notes.html", open_returns=open_returns, rows=rows)

    return sales_credit_notes


def build_supplier_debit_notes_view(deps):
    db = deps["db"]
    ensure_open_period = deps["ensure_open_period"]
    next_document_number = deps["next_document_number"]
    log_action = deps["log_action"]
    parse_positive_amount = deps["parse_positive_amount"]

    def supplier_debit_notes():
        conn = db()
        cur = conn.cursor()

        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            purchase_return_id = int(parse_positive_amount(request.form.get("purchase_return_id")) or 0)
            notes = request.form.get("notes", "").strip()
            cur.execute(
                """
                SELECT pr.id,pr.purchase_invoice_id,pi.supplier_id,pr.product_id,pr.quantity,pr.unit_price,pr.total,pr.tax_amount,pr.grand_total
                FROM purchase_returns pr
                JOIN purchase_invoices pi ON pi.id=pr.purchase_invoice_id
                WHERE pr.id=?
                """,
                (purchase_return_id,),
            )
            purchase_return = cur.fetchone()
            cur.execute("SELECT 1 FROM supplier_debit_notes WHERE purchase_return_id=?", (purchase_return_id,))
            existing = cur.fetchone()
            if not date_value:
                flash("تاريخ إشعار التسوية المدين مطلوب.", "danger")
            elif not purchase_return:
                flash("مردود المشتريات المحدد غير موجود.", "danger")
            elif existing:
                flash("تم إصدار إشعار تسوية مدين لهذا المردود من قبل.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("supplier_debit_notes"))
                doc_no = next_document_number(cur, "supplier_debit_notes")
                cur.execute(
                    """
                    INSERT INTO supplier_debit_notes(
                        date,doc_no,purchase_return_id,purchase_invoice_id,supplier_id,product_id,quantity,unit_price,total,tax_amount,grand_total,notes,status
                    )
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        date_value,
                        doc_no,
                        purchase_return[0],
                        purchase_return[1],
                        purchase_return[2],
                        purchase_return[3],
                        purchase_return[4],
                        purchase_return[5],
                        purchase_return[6],
                        purchase_return[7],
                        purchase_return[8],
                        notes,
                        "posted",
                    ),
                )
                note_id = cur.lastrowid
                log_action(cur, "create", "supplier_debit_note", note_id, f"{doc_no}; return_id={purchase_return_id}")
                conn.commit()
                conn.close()
                flash(f"تم إنشاء إشعار التسوية المدين {doc_no}.", "success")
                return redirect(url_for("supplier_debit_notes"))

        cur.execute(
            """
            SELECT pr.id,pr.date,s.name,p.name,pr.grand_total
            FROM purchase_returns pr
            JOIN purchase_invoices pi ON pi.id=pr.purchase_invoice_id
            LEFT JOIN suppliers s ON s.id=pi.supplier_id
            JOIN products p ON p.id=pr.product_id
            LEFT JOIN supplier_debit_notes sdn ON sdn.purchase_return_id=pr.id
            WHERE sdn.id IS NULL
            ORDER BY pr.id DESC
            """
        )
        open_returns = cur.fetchall()
        cur.execute(
            """
            SELECT sdn.id,sdn.date,sdn.doc_no,COALESCE(s.name,'مورد نقدي'),p.name,sdn.quantity,sdn.grand_total,sdn.purchase_return_id
            FROM supplier_debit_notes sdn
            LEFT JOIN suppliers s ON s.id=sdn.supplier_id
            LEFT JOIN products p ON p.id=sdn.product_id
            ORDER BY sdn.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("supplier_debit_notes.html", open_returns=open_returns, rows=rows)

    return supplier_debit_notes
