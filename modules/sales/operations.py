from flask import flash, redirect, render_template, request, url_for
import sqlite3

from modules.sales.taxing import invoice_totals, parse_flag, taxable_line


def _refresh_sales_order_status(cur, sales_order_id):
    if not sales_order_id:
        return
    cur.execute("SELECT COALESCE(SUM(quantity),0) FROM sales_order_lines WHERE order_id=?", (sales_order_id,))
    ordered_total = cur.fetchone()[0] or 0
    cur.execute(
        """
        SELECT COALESCE(SUM(delivered_quantity),0)
        FROM sales_delivery_notes
        WHERE sales_order_id=?
          AND status!='cancelled'
        """,
        (sales_order_id,),
    )
    delivered_total = cur.fetchone()[0] or 0
    if delivered_total <= 0:
        status = "issued"
    elif delivered_total >= ordered_total:
        status = "completed"
    else:
        status = "partial"
    cur.execute("UPDATE sales_orders SET status=? WHERE id=?", (status, sales_order_id))


def _refresh_purchase_order_status(cur, purchase_order_id):
    if not purchase_order_id:
        return
    cur.execute("SELECT COALESCE(SUM(quantity),0) FROM purchase_order_lines WHERE order_id=?", (purchase_order_id,))
    ordered_total = cur.fetchone()[0] or 0
    cur.execute(
        """
        SELECT COALESCE(SUM(received_quantity),0)
        FROM purchase_receipts
        WHERE purchase_order_id=?
          AND status!='cancelled'
        """,
        (purchase_order_id,),
    )
    received_total = cur.fetchone()[0] or 0
    if received_total <= 0:
        status = "issued"
    elif received_total >= ordered_total:
        status = "completed"
    else:
        status = "partial"
    cur.execute("UPDATE purchase_orders SET status=? WHERE id=?", (status, purchase_order_id))


def build_cancel_sale_view(deps):
    db = deps["db"]
    reverse_journal = deps["reverse_journal"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]

    def cancel_sale(id):
        reason = request.form.get("reason", "").strip() or "إلغاء مستند"
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT date,product_id,quantity,journal_id,tax_journal_id,withholding_journal_id,cogs_journal_id,status,sales_order_id
            FROM sales_invoices
            WHERE id=?
            """,
            (id,),
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            flash("فاتورة البيع غير موجودة.", "danger")
            return redirect(url_for("sales"))
        date_value, product_id, quantity, journal_id, tax_journal_id, withholding_journal_id, cogs_journal_id, status, sales_order_id = row
        if status == "cancelled":
            conn.close()
            flash("فاتورة البيع ملغاة بالفعل.", "warning")
            return redirect(url_for("sales"))
        if status == "draft":
            cur.execute("UPDATE sales_invoices SET status='cancelled', cancelled_at=CURRENT_TIMESTAMP, cancel_reason=? WHERE id=?", (reason, id))
            log_action(cur, "cancel", "sales_invoice", id, reason)
            conn.commit()
            conn.close()
            flash("تم إلغاء مسودة فاتورة البيع بدون أي أثر محاسبي أو مخزني.", "success")
            return redirect(url_for("sales"))
        reverse_journal(cur, journal_id, date_value, reason)
        reverse_journal(cur, tax_journal_id, date_value, reason)
        reverse_journal(cur, withholding_journal_id, date_value, reason)
        reverse_journal(cur, cogs_journal_id, date_value, reason)
        cur.execute(
            """
            SELECT id,date,sales_order_id,product_id,COALESCE(quantity_base, delivered_quantity),cogs_journal_id,status
            FROM sales_delivery_notes
            WHERE invoice_id=?
            ORDER BY id
            """,
            (id,),
        )
        linked_deliveries = cur.fetchall()
        if linked_deliveries:
            for delivery_id, delivery_date, linked_order_id, line_product_id, delivered_quantity, delivery_cogs_journal_id, delivery_status in linked_deliveries:
                if delivery_status == "cancelled":
                    continue
                reverse_journal(cur, delivery_cogs_journal_id, delivery_date or date_value, reason)
                cur.execute("UPDATE products SET stock_quantity=stock_quantity+? WHERE id=?", (delivered_quantity, line_product_id))
                cur.execute(
                    """
                    INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (delivery_date or date_value, line_product_id, "cancel_in", delivered_quantity, "sales_delivery_cancel", delivery_id, reason),
                )
                cur.execute(
                    """
                    UPDATE sales_delivery_notes
                    SET status='cancelled', invoice_id=NULL, cancelled_at=CURRENT_TIMESTAMP, cancel_reason=?
                    WHERE id=?
                    """,
                    (reason, delivery_id),
                )
                _refresh_sales_order_status(cur, linked_order_id)
        else:
            cur.execute(
                """
                SELECT product_id,COALESCE(quantity_base, quantity)
                FROM sales_invoice_lines
                WHERE invoice_id=?
                ORDER BY id
                """,
                (id,),
            )
            line_rows = cur.fetchall()
            if not line_rows:
                line_rows = [(product_id, quantity)]
            for line_product_id, line_quantity in line_rows:
                cur.execute("UPDATE products SET stock_quantity=stock_quantity+? WHERE id=?", (line_quantity, line_product_id))
                cur.execute(
                    """
                    INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (date_value, line_product_id, "cancel_in", line_quantity, "sale_cancel", id, reason),
                )
            _refresh_sales_order_status(cur, sales_order_id)
        cur.execute("UPDATE sales_invoices SET status='cancelled', cancelled_at=CURRENT_TIMESTAMP, cancel_reason=? WHERE id=?", (reason, id))
        log_action(cur, "cancel", "sales_invoice", id, reason)
        conn.commit()
        conn.close()
        rebuild_ledger()
        flash("تم إلغاء فاتورة البيع وعكس القيود والمخزون وتحديث المستندات المرتبطة.", "success")
        return redirect(url_for("sales_invoices"))

    return cancel_sale


def build_edit_sale_invoice_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    log_action = deps["log_action"]
    default_tax_rate = deps["DEFAULT_TAX_RATE"]

    def edit_sale_invoice(id):
        from modules.sales.views import _build_product_units_map, _customer_withholding, _invoice_form_lines, _invoice_number_exists

        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT s.id,s.date,s.due_date,s.customer_id,s.tax_rate,s.payment_type,s.status,
                   COALESCE(l.vat_enabled,1),COALESCE(l.withholding_enabled,CASE WHEN COALESCE(s.withholding_rate,0)>0 THEN 1 ELSE 0 END),
                   COALESCE(l.vat_rate,s.tax_rate,14),COALESCE(l.withholding_rate,s.withholding_rate,1),
                   COALESCE(s.notes,''),COALESCE(s.po_ref,''),COALESCE(s.gr_ref,''),COALESCE(s.invoice_number,s.doc_no,'')
            FROM sales_invoices s
            LEFT JOIN sales_invoice_lines l ON l.invoice_id=s.id
            WHERE s.id=?
            ORDER BY l.id
            LIMIT 1
            """,
            (id,),
        )
        invoice = cur.fetchone()
        if not invoice:
            conn.close()
            flash("فاتورة البيع غير موجودة.", "danger")
            return redirect(url_for("sales_invoices"))
        if invoice[6] != "draft":
            conn.close()
            flash("لا يمكن تعديل فاتورة مرحلة.", "danger")
            return redirect(url_for("sales_invoices"))
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            invoice_number = (request.form.get("invoice_number") or "").strip() or (invoice[14] or "")
            due_date = request.form.get("due_date", "").strip()
            customer_id = request.form.get("customer_id") or None
            payment_type = request.form.get("payment_type", "cash")
            notes = request.form.get("notes", "").strip()
            po_ref = request.form.get("po_ref", "").strip()
            gr_ref = request.form.get("gr_ref", "").strip()
            _, default_withholding_rate = _customer_withholding(cur, customer_id)
            vat_enabled = parse_flag(request.form.get("vat_enabled"), True)
            withholding_enabled = parse_flag(request.form.get("withholding_enabled"), default_withholding_rate > 0)
            vat_rate = parse_positive_amount(request.form.get("vat_rate", request.form.get("tax_rate", default_tax_rate)))
            withholding_rate = parse_positive_amount(request.form.get("withholding_rate", default_withholding_rate or 1))
            lines = _invoice_form_lines(cur, deps, "sale", vat_rate, withholding_rate, withholding_enabled)
            if not date_value or not lines:
                flash("راجع بيانات الفاتورة قبل الحفظ.", "danger")
            elif payment_type == "credit" and not customer_id:
                flash("اختر العميل عند البيع الآجل.", "danger")
            elif _invoice_number_exists(cur, "sales_invoices", invoice_number, exclude_id=id):
                flash("رقم الفاتورة مستخدم بالفعل", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("sales_invoices"))
                totals = {
                    "quantity": round(sum(line["quantity"] for line in lines), 4),
                    "total": round(sum(line["total"] for line in lines), 2),
                    "cost_total": round(sum(line["cost_total"] for line in lines), 2),
                    "tax_amount": round(sum(line["tax_amount"] for line in lines), 2),
                    "withholding_amount": round(sum(line["withholding_amount"] for line in lines), 2),
                    "grand_total": round(sum(line["grand_total"] for line in lines), 2),
                }
                first_line = lines[0]
                try:
                    cur.execute(
                        """
                        UPDATE sales_invoices
                        SET date=?,due_date=?,doc_no=?,invoice_number=?,customer_id=?,product_id=?,quantity=?,unit_price=?,total=?,cost_total=?,tax_rate=?,tax_amount=?,
                            withholding_rate=?,withholding_amount=?,grand_total=?,payment_type=?,notes=?,po_ref=?,gr_ref=?
                        WHERE id=?
                        """,
                        (
                            date_value, due_date, invoice_number, invoice_number, customer_id, first_line["product_id"], totals["quantity"], first_line["unit_price"], totals["total"],
                            totals["cost_total"], vat_rate, totals["tax_amount"], withholding_rate, totals["withholding_amount"], totals["grand_total"],
                            payment_type, notes, po_ref, gr_ref, id,
                        ),
                    )
                except sqlite3.IntegrityError:
                    conn.rollback()
                    flash("رقم الفاتورة مستخدم بالفعل", "danger")
                    conn.close()
                    return redirect(url_for("sales_invoices"))
                cur.execute("DELETE FROM sales_invoice_lines WHERE invoice_id=?", (id,))
                for line in lines:
                    cur.execute(
                        """
                        INSERT INTO sales_invoice_lines(
                            invoice_id,product_id,quantity,unit_price,total,cost_total,vat_enabled,withholding_enabled,vat_rate,withholding_rate,vat_amount,withholding_amount,grand_total,
                            unit_id,unit_name,conversion_factor,quantity_base,selected_unit,qty,base_qty
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            id, line["product_id"], line["quantity"], line["unit_price"], line["total"], line["cost_total"],
                            1 if vat_enabled else 0, 1 if withholding_enabled else 0, line["tax_rate"], line["withholding_rate"],
                            line["tax_amount"], line["withholding_amount"], line["grand_total"], line["unit_id"], line["unit_name"],
                            line["conversion_factor"], line["quantity_base"], line["selected_unit"], line["quantity"], line["quantity_base"],
                        ),
                    )
                log_action(cur, "update", "sales_invoice", id, "draft multi-line edit")
                conn.commit()
                conn.close()
                flash("تم تعديل فاتورة البيع غير المرحلة.", "success")
                return redirect(url_for("sales_invoices"))
        cur.execute(
            """
            SELECT product_id,quantity,unit_price,COALESCE(vat_rate, ?),COALESCE(unit_id, 0),COALESCE(unit_name, ''),COALESCE(conversion_factor, 1)
            FROM sales_invoice_lines
            WHERE invoice_id=?
            ORDER BY id
            """,
            (default_tax_rate, id),
        )
        invoice_lines = cur.fetchall()
        cur.execute("SELECT id,name FROM customers ORDER BY name")
        customers_rows = cur.fetchall()
        product_rows, product_units_map = _build_product_units_map(cur, "sale")
        conn.close()
        return render_template(
            "edit_invoice_multi.html",
            invoice_kind="sale",
            invoice=invoice,
            lines=invoice_lines,
            customers=customers_rows,
            suppliers=[],
            products=product_rows,
            product_units_json=__import__("json").dumps(product_units_map, ensure_ascii=False),
        )

    return edit_sale_invoice


def build_cancel_purchase_view(deps):
    db = deps["db"]
    reverse_journal = deps["reverse_journal"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]

    def cancel_purchase(id):
        reason = request.form.get("reason", "").strip() or "إلغاء مستند"
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT date,product_id,quantity,journal_id,tax_journal_id,withholding_journal_id,status,purchase_order_id
            FROM purchase_invoices
            WHERE id=?
            """,
            (id,),
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            flash("فاتورة المشتريات غير موجودة.", "danger")
            return redirect(url_for("purchases"))
        date_value, product_id, quantity, journal_id, tax_journal_id, withholding_journal_id, status, purchase_order_id = row
        if status == "cancelled":
            conn.close()
            flash("فاتورة المشتريات ملغاة بالفعل.", "warning")
            return redirect(url_for("purchases"))
        if status == "draft":
            cur.execute("UPDATE purchase_invoices SET status='cancelled', cancelled_at=CURRENT_TIMESTAMP, cancel_reason=? WHERE id=?", (reason, id))
            log_action(cur, "cancel", "purchase_invoice", id, reason)
            conn.commit()
            conn.close()
            flash("تم إلغاء مسودة فاتورة المشتريات بدون أي أثر محاسبي أو مخزني.", "success")
            return redirect(url_for("purchases"))
        reverse_journal(cur, journal_id, date_value, reason)
        reverse_journal(cur, tax_journal_id, date_value, reason)
        reverse_journal(cur, withholding_journal_id, date_value, reason)
        cur.execute(
            """
            SELECT id,date,purchase_order_id,product_id,COALESCE(quantity_base, received_quantity),journal_id,status
            FROM purchase_receipts
            WHERE invoice_id=?
            ORDER BY id
            """,
            (id,),
        )
        linked_receipts = cur.fetchall()
        if linked_receipts:
            for receipt_id, receipt_date, linked_order_id, line_product_id, received_quantity, receipt_journal_id, receipt_status in linked_receipts:
                if receipt_status == "cancelled":
                    continue
                cur.execute("SELECT stock_quantity FROM products WHERE id=?", (line_product_id,))
                stock_row = cur.fetchone()
                if not stock_row or (stock_row[0] or 0) < received_quantity:
                    conn.close()
                    flash("لا يمكن إلغاء فاتورة المشتريات لأن المخزون الحالي لا يكفي لعكس إذن الاستلام المرتبط.", "danger")
                    return redirect(url_for("purchases"))
                reverse_journal(cur, receipt_journal_id, receipt_date or date_value, reason)
                cur.execute("UPDATE products SET stock_quantity=stock_quantity-? WHERE id=?", (received_quantity, line_product_id))
                cur.execute(
                    """
                    INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (receipt_date or date_value, line_product_id, "cancel_out", -received_quantity, "purchase_receipt_cancel", receipt_id, reason),
                )
                cur.execute(
                    """
                    UPDATE purchase_receipts
                    SET status='cancelled', invoice_id=NULL, cancelled_at=CURRENT_TIMESTAMP, cancel_reason=?
                    WHERE id=?
                    """,
                    (reason, receipt_id),
                )
                _refresh_purchase_order_status(cur, linked_order_id)
        else:
            cur.execute(
                """
                SELECT product_id,COALESCE(quantity_base, quantity)
                FROM purchase_invoice_lines
                WHERE invoice_id=?
                ORDER BY id
                """,
                (id,),
            )
            line_rows = cur.fetchall()
            if not line_rows:
                line_rows = [(product_id, quantity)]
            for line_product_id, line_quantity in line_rows:
                cur.execute("SELECT stock_quantity FROM products WHERE id=?", (line_product_id,))
                stock_row = cur.fetchone()
                if not stock_row or (stock_row[0] or 0) < line_quantity:
                    conn.close()
                    flash("لا يمكن إلغاء فاتورة المشتريات لأن رصيد المخزون الحالي لا يكفي لعكس الحركة.", "danger")
                    return redirect(url_for("purchases"))
                cur.execute("UPDATE products SET stock_quantity=stock_quantity-? WHERE id=?", (line_quantity, line_product_id))
                cur.execute(
                    """
                    INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (date_value, line_product_id, "cancel_out", -line_quantity, "purchase_cancel", id, reason),
                )
            _refresh_purchase_order_status(cur, purchase_order_id)
        cur.execute("UPDATE purchase_invoices SET status='cancelled', cancelled_at=CURRENT_TIMESTAMP, cancel_reason=? WHERE id=?", (reason, id))
        log_action(cur, "cancel", "purchase_invoice", id, reason)
        conn.commit()
        conn.close()
        rebuild_ledger()
        flash("تم إلغاء فاتورة المشتريات وعكس القيود والمخزون وتحديث المستندات المرتبطة.", "success")
        return redirect(url_for("purchase_invoices"))

    return cancel_purchase


def build_edit_purchase_invoice_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    log_action = deps["log_action"]
    default_tax_rate = deps["DEFAULT_TAX_RATE"]

    def edit_purchase_invoice(id):
        from modules.sales.views import _build_product_units_map, _invoice_form_lines, _supplier_withholding, _invoice_number_exists

        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT p.id,p.date,p.supplier_invoice_no,p.supplier_invoice_date,p.due_date,p.supplier_id,p.tax_rate,p.payment_type,p.notes,p.status,
                   COALESCE(l.vat_enabled,1),COALESCE(l.withholding_enabled,CASE WHEN COALESCE(p.withholding_rate,0)>0 THEN 1 ELSE 0 END),
                   COALESCE(l.vat_rate,p.tax_rate,14),COALESCE(l.withholding_rate,p.withholding_rate,1),COALESCE(p.invoice_number,p.doc_no,'')
            FROM purchase_invoices p
            LEFT JOIN purchase_invoice_lines l ON l.invoice_id=p.id
            WHERE p.id=?
            ORDER BY l.id
            LIMIT 1
            """,
            (id,),
        )
        invoice = cur.fetchone()
        if not invoice:
            conn.close()
            flash("فاتورة المورد غير موجودة.", "danger")
            return redirect(url_for("purchase_invoices"))
        if invoice[9] != "draft":
            conn.close()
            flash("لا يمكن تعديل فاتورة مرحلة.", "danger")
            return redirect(url_for("purchase_invoices"))
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            invoice_number = (request.form.get("invoice_number") or "").strip() or (invoice[14] or "")
            supplier_invoice_no = request.form.get("supplier_invoice_no", "").strip()
            supplier_invoice_date = request.form.get("supplier_invoice_date", "").strip()
            due_date = request.form.get("due_date", "").strip()
            supplier_id = request.form.get("supplier_id") or None
            payment_type = request.form.get("payment_type", "cash")
            notes = request.form.get("notes", "").strip()
            _, default_withholding_rate = _supplier_withholding(cur, supplier_id)
            vat_enabled = parse_flag(request.form.get("vat_enabled"), True)
            withholding_enabled = parse_flag(request.form.get("withholding_enabled"), default_withholding_rate > 0)
            vat_rate = parse_positive_amount(request.form.get("vat_rate", request.form.get("tax_rate", default_tax_rate)))
            withholding_rate = parse_positive_amount(request.form.get("withholding_rate", default_withholding_rate or 1))
            lines = _invoice_form_lines(cur, deps, "purchase", vat_rate, withholding_rate, withholding_enabled)
            if not date_value or not supplier_invoice_no or not supplier_invoice_date or not lines:
                flash("راجع بيانات فاتورة المورد قبل الحفظ.", "danger")
            elif payment_type == "credit" and not supplier_id:
                flash("اختر المورد عند الشراء الآجل.", "danger")
            elif _invoice_number_exists(cur, "purchase_invoices", invoice_number, exclude_id=id):
                flash("رقم الفاتورة مستخدم بالفعل", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("purchase_invoices"))
                totals = {
                    "quantity": round(sum(line["quantity"] for line in lines), 4),
                    "total": round(sum(line["total"] for line in lines), 2),
                    "tax_amount": round(sum(line["tax_amount"] for line in lines), 2),
                    "withholding_amount": round(sum(line["withholding_amount"] for line in lines), 2),
                    "grand_total": round(sum(line["grand_total"] for line in lines), 2),
                }
                first_line = lines[0]
                try:
                    cur.execute(
                        """
                        UPDATE purchase_invoices
                        SET date=?,doc_no=?,invoice_number=?,supplier_invoice_no=?,supplier_invoice_date=?,due_date=?,supplier_id=?,product_id=?,quantity=?,unit_price=?,total=?,
                            tax_rate=?,tax_amount=?,withholding_rate=?,withholding_amount=?,grand_total=?,payment_type=?,notes=?
                        WHERE id=?
                        """,
                        (
                            date_value, invoice_number, invoice_number, supplier_invoice_no, supplier_invoice_date, due_date, supplier_id, first_line["product_id"], totals["quantity"],
                            first_line["unit_price"], totals["total"], vat_rate, totals["tax_amount"], withholding_rate, totals["withholding_amount"],
                            totals["grand_total"], payment_type, notes, id,
                        ),
                    )
                except sqlite3.IntegrityError:
                    conn.rollback()
                    flash("رقم الفاتورة مستخدم بالفعل", "danger")
                    conn.close()
                    return redirect(url_for("purchase_invoices"))
                cur.execute("DELETE FROM purchase_invoice_lines WHERE invoice_id=?", (id,))
                for line in lines:
                    cur.execute(
                        """
                        INSERT INTO purchase_invoice_lines(
                            invoice_id,product_id,quantity,unit_price,total,vat_enabled,withholding_enabled,vat_rate,withholding_rate,vat_amount,withholding_amount,grand_total,
                            unit_id,unit_name,conversion_factor,quantity_base,selected_unit,qty,base_qty
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            id, line["product_id"], line["quantity"], line["unit_price"], line["total"], 1 if vat_enabled else 0,
                            1 if withholding_enabled else 0, line["tax_rate"], line["withholding_rate"], line["tax_amount"], line["withholding_amount"],
                            line["grand_total"], line["unit_id"], line["unit_name"], line["conversion_factor"], line["quantity_base"],
                            line["selected_unit"], line["quantity"], line["quantity_base"],
                        ),
                    )
                log_action(cur, "update", "purchase_invoice", id, "draft multi-line edit")
                conn.commit()
                conn.close()
                flash("تم تعديل فاتورة المورد غير المرحلة.", "success")
                return redirect(url_for("purchase_invoices"))
        cur.execute(
            """
            SELECT product_id,quantity,unit_price,COALESCE(vat_rate, ?),COALESCE(unit_id, 0),COALESCE(unit_name, ''),COALESCE(conversion_factor, 1)
            FROM purchase_invoice_lines
            WHERE invoice_id=?
            ORDER BY id
            """,
            (default_tax_rate, id),
        )
        invoice_lines = cur.fetchall()
        cur.execute("SELECT id,name FROM suppliers ORDER BY name")
        suppliers_rows = cur.fetchall()
        product_rows, product_units_map = _build_product_units_map(cur, "purchase")
        conn.close()
        return render_template(
            "edit_invoice_multi.html",
            invoice_kind="purchase",
            invoice=invoice,
            lines=invoice_lines,
            customers=[],
            suppliers=suppliers_rows,
            products=product_rows,
            product_units_json=__import__("json").dumps(product_units_map, ensure_ascii=False),
        )

    return edit_purchase_invoice


def build_cancel_receipt_view(deps):
    db = deps["db"]
    reverse_journal = deps["reverse_journal"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]

    def cancel_receipt(id):
        reason = request.form.get("reason", "").strip() or "ط¥ظ„ط؛ط§ط، ط³ظ†ط¯"
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT date,journal_id,status FROM receipt_vouchers WHERE id=?", (id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            flash("ط³ظ†ط¯ ط§ظ„ظ‚ط¨ط¶ ط؛ظٹط± ظ…ظˆط¬ظˆط¯.", "danger")
            return redirect(url_for("receipts"))
        date_value, journal_id, status = row
        if status == "cancelled":
            conn.close()
            flash("ط³ظ†ط¯ ط§ظ„ظ‚ط¨ط¶ ظ…ظ„ط؛ظ‰ ط¨ط§ظ„ظپط¹ظ„.", "warning")
            return redirect(url_for("receipts"))
        if status == "draft":
            cur.execute("UPDATE receipt_vouchers SET status='cancelled', cancelled_at=CURRENT_TIMESTAMP, cancel_reason=? WHERE id=?", (reason, id))
            log_action(cur, "cancel", "receipt_voucher", id, reason)
            conn.commit()
            conn.close()
            flash("طھظ… ط¥ظ„ط؛ط§ط، ظ…ط³ظˆط¯ط© ط³ظ†ط¯ ط§ظ„ظ‚ط¨ط¶ ط¨ط¯ظˆظ† ط£ط«ط± ظ…ط­ط§ط³ط¨ظٹ.", "success")
            return redirect(url_for("receipts"))
        reverse_journal(cur, journal_id, date_value, reason)
        cur.execute("UPDATE receipt_vouchers SET status='cancelled', cancelled_at=CURRENT_TIMESTAMP, cancel_reason=? WHERE id=?", (reason, id))
        log_action(cur, "cancel", "receipt_voucher", id, reason)
        conn.commit()
        conn.close()
        rebuild_ledger()
        flash("طھظ… ط¥ظ„ط؛ط§ط، ط³ظ†ط¯ ط§ظ„ظ‚ط¨ط¶ ظˆط¹ظƒط³ ط§ظ„ظ‚ظٹط¯.", "success")
        return redirect(url_for("receipts"))

    return cancel_receipt


def build_edit_receipt_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    log_action = deps["log_action"]

    def edit_receipt(id):
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT id,date,customer_id,amount,notes,status FROM receipt_vouchers WHERE id=?", (id,))
        voucher = cur.fetchone()
        if not voucher:
            conn.close()
            flash("ط³ظ†ط¯ ط§ظ„ظ‚ط¨ط¶ ط؛ظٹط± ظ…ظˆط¬ظˆط¯.", "danger")
            return redirect(url_for("receipts"))
        if voucher[5] != "draft":
            conn.close()
            flash("ظ„ط§ ظٹظ…ظƒظ† طھط¹ط¯ظٹظ„ ط³ظ†ط¯ ظ…ط±ط­ظ„. ظپظƒ طھط±ط­ظٹظ„ ظ…ط¬ظ…ظˆط¹ط© ط³ظ†ط¯ط§طھ ط§ظ„ظ‚ط¨ط¶ ط£ظˆظ„ط§.", "danger")
            return redirect(url_for("receipts"))
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            customer_id = request.form.get("customer_id")
            amount = parse_positive_amount(request.form.get("amount"))
            notes = request.form.get("notes", "").strip()
            if not date_value or not customer_id or amount <= 0:
                flash("ط±ط§ط¬ط¹ ط¨ظٹط§ظ†ط§طھ ط³ظ†ط¯ ط§ظ„ظ‚ط¨ط¶.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("receipts"))
                cur.execute("UPDATE receipt_vouchers SET date=?,customer_id=?,amount=?,notes=? WHERE id=?", (date_value, customer_id, amount, notes, id))
                log_action(cur, "update", "receipt_voucher", id, "طھط¹ط¯ظٹظ„ ظ…ط³ظˆط¯ط©")
                conn.commit()
                conn.close()
                flash("طھظ… طھط¹ط¯ظٹظ„ ط³ظ†ط¯ ط§ظ„ظ‚ط¨ط¶ ط؛ظٹط± ط§ظ„ظ…ط±ط­ظ„.", "success")
                return redirect(url_for("receipts"))
        cur.execute("SELECT id,name FROM customers ORDER BY name")
        customers_rows = cur.fetchall()
        conn.close()
        return render_template("edit_voucher.html", voucher=voucher, parties=customers_rows, party_field="customer_id", title="طھط¹ط¯ظٹظ„ ط³ظ†ط¯ ظ‚ط¨ط¶", back_endpoint="receipts")

    return edit_receipt


def build_cancel_payment_view(deps):
    db = deps["db"]
    reverse_journal = deps["reverse_journal"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]

    def cancel_payment(id):
        reason = request.form.get("reason", "").strip() or "ط¥ظ„ط؛ط§ط، ط³ظ†ط¯"
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT date,journal_id,status FROM payment_vouchers WHERE id=?", (id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            flash("ط³ظ†ط¯ ط§ظ„طµط±ظپ ط؛ظٹط± ظ…ظˆط¬ظˆط¯.", "danger")
            return redirect(url_for("payments"))
        date_value, journal_id, status = row
        if status == "cancelled":
            conn.close()
            flash("ط³ظ†ط¯ ط§ظ„طµط±ظپ ظ…ظ„ط؛ظ‰ ط¨ط§ظ„ظپط¹ظ„.", "warning")
            return redirect(url_for("payments"))
        if status == "draft":
            cur.execute("UPDATE payment_vouchers SET status='cancelled', cancelled_at=CURRENT_TIMESTAMP, cancel_reason=? WHERE id=?", (reason, id))
            log_action(cur, "cancel", "payment_voucher", id, reason)
            conn.commit()
            conn.close()
            flash("طھظ… ط¥ظ„ط؛ط§ط، ظ…ط³ظˆط¯ط© ط³ظ†ط¯ ط§ظ„طµط±ظپ ط¨ط¯ظˆظ† ط£ط«ط± ظ…ط­ط§ط³ط¨ظٹ.", "success")
            return redirect(url_for("payments"))
        reverse_journal(cur, journal_id, date_value, reason)
        cur.execute("UPDATE payment_vouchers SET status='cancelled', cancelled_at=CURRENT_TIMESTAMP, cancel_reason=? WHERE id=?", (reason, id))
        log_action(cur, "cancel", "payment_voucher", id, reason)
        conn.commit()
        conn.close()
        rebuild_ledger()
        flash("طھظ… ط¥ظ„ط؛ط§ط، ط³ظ†ط¯ ط§ظ„طµط±ظپ ظˆط¹ظƒط³ ط§ظ„ظ‚ظٹط¯.", "success")
        return redirect(url_for("payments"))

    return cancel_payment


def build_edit_payment_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    log_action = deps["log_action"]

    def edit_payment(id):
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT id,date,supplier_id,amount,notes,status FROM payment_vouchers WHERE id=?", (id,))
        voucher = cur.fetchone()
        if not voucher:
            conn.close()
            flash("ط³ظ†ط¯ ط§ظ„طµط±ظپ ط؛ظٹط± ظ…ظˆط¬ظˆط¯.", "danger")
            return redirect(url_for("payments"))
        if voucher[5] != "draft":
            conn.close()
            flash("ظ„ط§ ظٹظ…ظƒظ† طھط¹ط¯ظٹظ„ ط³ظ†ط¯ ظ…ط±ط­ظ„. ظپظƒ طھط±ط­ظٹظ„ ظ…ط¬ظ…ظˆط¹ط© ط³ظ†ط¯ط§طھ ط§ظ„طµط±ظپ ط£ظˆظ„ط§.", "danger")
            return redirect(url_for("payments"))
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            supplier_id = request.form.get("supplier_id")
            amount = parse_positive_amount(request.form.get("amount"))
            notes = request.form.get("notes", "").strip()
            if not date_value or not supplier_id or amount <= 0:
                flash("ط±ط§ط¬ط¹ ط¨ظٹط§ظ†ط§طھ ط³ظ†ط¯ ط§ظ„طµط±ظپ.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("payments"))
                cur.execute("UPDATE payment_vouchers SET date=?,supplier_id=?,amount=?,notes=? WHERE id=?", (date_value, supplier_id, amount, notes, id))
                log_action(cur, "update", "payment_voucher", id, "طھط¹ط¯ظٹظ„ ظ…ط³ظˆط¯ط©")
                conn.commit()
                conn.close()
                flash("طھظ… طھط¹ط¯ظٹظ„ ط³ظ†ط¯ ط§ظ„طµط±ظپ ط؛ظٹط± ط§ظ„ظ…ط±ط­ظ„.", "success")
                return redirect(url_for("payments"))
        cur.execute("SELECT id,name FROM suppliers ORDER BY name")
        suppliers_rows = cur.fetchall()
        conn.close()
        return render_template("edit_voucher.html", voucher=voucher, parties=suppliers_rows, party_field="supplier_id", title="طھط¹ط¯ظٹظ„ ط³ظ†ط¯ طµط±ظپ", back_endpoint="payments")

    return edit_payment


def build_allocations_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    log_action = deps["log_action"]

    def allocations():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            allocation_type = request.form.get("allocation_type", "customer")
            invoice_id = int(parse_positive_amount(request.form.get("invoice_id")) or 0)
            voucher_id = int(parse_positive_amount(request.form.get("voucher_id")) or 0)
            amount = parse_positive_amount(request.form.get("amount"))
            if allocation_type not in ("customer", "supplier") or invoice_id <= 0 or voucher_id <= 0 or amount <= 0:
                flash("ط±ط§ط¬ط¹ ط¨ظٹط§ظ†ط§طھ ط§ظ„طھط®طµظٹطµ.", "danger")
            else:
                if allocation_type == "customer":
                    cur.execute("SELECT grand_total,customer_id FROM sales_invoices WHERE id=? AND status='posted' AND payment_type='credit'", (invoice_id,))
                    invoice = cur.fetchone()
                    cur.execute("SELECT amount,customer_id FROM receipt_vouchers WHERE id=? AND status='posted'", (voucher_id,))
                    voucher = cur.fetchone()
                else:
                    cur.execute("SELECT grand_total,supplier_id FROM purchase_invoices WHERE id=? AND status='posted' AND payment_type='credit'", (invoice_id,))
                    invoice = cur.fetchone()
                    cur.execute("SELECT amount,supplier_id FROM payment_vouchers WHERE id=? AND status='posted'", (voucher_id,))
                    voucher = cur.fetchone()
                if not invoice or not voucher:
                    flash("ط§ظ„ظپط§طھظˆط±ط© ط£ظˆ ط§ظ„ط³ظ†ط¯ ط؛ظٹط± ظ…ظˆط¬ظˆط¯ ط£ظˆ ط؛ظٹط± ظ…ط±ط­ظ„.", "danger")
                elif invoice[1] != voucher[1]:
                    flash("ظ„ط§ ظٹظ…ظƒظ† ط±ط¨ط· ط³ظ†ط¯ ط¨ط·ط±ظپ ظ…ط®طھظ„ظپ ط¹ظ† ط·ط±ظپ ط§ظ„ظپط§طھظˆط±ط©.", "danger")
                else:
                    cur.execute("SELECT COALESCE(SUM(amount),0) FROM invoice_allocations WHERE allocation_type=? AND invoice_id=?", (allocation_type, invoice_id))
                    allocated_invoice = cur.fetchone()[0]
                    cur.execute("SELECT COALESCE(SUM(amount),0) FROM invoice_allocations WHERE allocation_type=? AND voucher_id=?", (allocation_type, voucher_id))
                    allocated_voucher = cur.fetchone()[0]
                    if allocated_invoice + amount > invoice[0]:
                        flash("ظ…ط¨ظ„ط؛ ط§ظ„ط±ط¨ط· ط£ظƒط¨ط± ظ…ظ† ط§ظ„ظ…طھط¨ظ‚ظٹ ط¹ظ„ظ‰ ط§ظ„ظپط§طھظˆط±ط©.", "danger")
                    elif allocated_voucher + amount > voucher[0]:
                        flash("ظ…ط¨ظ„ط؛ ط§ظ„ط±ط¨ط· ط£ظƒط¨ط± ظ…ظ† ط§ظ„ظ…طھط¨ظ‚ظٹ ظپظٹ ط§ظ„ط³ظ†ط¯.", "danger")
                    else:
                        cur.execute("INSERT INTO invoice_allocations(allocation_type,invoice_id,voucher_id,amount) VALUES (?,?,?,?)", (allocation_type, invoice_id, voucher_id, amount))
                        allocation_id = cur.lastrowid
                        log_action(cur, "create", "invoice_allocation", allocation_id, f"{allocation_type}:{amount}")
                        conn.commit()
                        flash("طھظ… ط±ط¨ط· ط§ظ„ط³ط¯ط§ط¯/ط§ظ„طھط­طµظٹظ„ ط¨ط§ظ„ظپط§طھظˆط±ط©.", "success")
                        return redirect(url_for("allocations"))
        cur.execute("SELECT id,date,grand_total FROM sales_invoices WHERE status='posted' AND payment_type='credit' ORDER BY id DESC")
        sales_invoices_rows = cur.fetchall()
        cur.execute("SELECT id,date,grand_total FROM purchase_invoices WHERE status='posted' AND payment_type='credit' ORDER BY id DESC")
        purchase_invoices_rows = cur.fetchall()
        cur.execute("SELECT id,date,amount FROM receipt_vouchers WHERE status='posted' ORDER BY id DESC")
        receipts_rows = cur.fetchall()
        cur.execute("SELECT id,date,amount FROM payment_vouchers WHERE status='posted' ORDER BY id DESC")
        payments_rows = cur.fetchall()
        cur.execute("SELECT allocation_type,invoice_id,voucher_id,amount FROM invoice_allocations ORDER BY id DESC LIMIT 100")
        rows = cur.fetchall()
        conn.close()
        return render_template("allocations.html", rows=rows, sales_invoices=sales_invoices_rows, purchase_invoices=purchase_invoices_rows, receipts=receipts_rows, payments=payments_rows)

    return allocations


