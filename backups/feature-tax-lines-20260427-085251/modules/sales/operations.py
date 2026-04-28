from flask import flash, redirect, render_template, request, url_for


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
            SELECT date,product_id,quantity,journal_id,tax_journal_id,withholding_journal_id,cogs_journal_id,status
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
        date_value, product_id, quantity, journal_id, tax_journal_id, withholding_journal_id, cogs_journal_id, status = row
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
        cur.execute("UPDATE products SET stock_quantity=stock_quantity+? WHERE id=?", (quantity, product_id))
        cur.execute(
            """
            INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes)
            VALUES (?,?,?,?,?,?,?)
            """,
            (date_value, product_id, "cancel_in", quantity, "sale_cancel", id, reason),
        )
        cur.execute("UPDATE sales_invoices SET status='cancelled', cancelled_at=CURRENT_TIMESTAMP, cancel_reason=? WHERE id=?", (reason, id))
        log_action(cur, "cancel", "sales_invoice", id, reason)
        conn.commit()
        conn.close()
        rebuild_ledger()
        flash("تم إلغاء فاتورة البيع وعكس القيود وتحديث المخزون.", "success")
        return redirect(url_for("sales"))

    return cancel_sale


def build_edit_sale_invoice_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    log_action = deps["log_action"]
    default_tax_rate = deps["DEFAULT_TAX_RATE"]

    def edit_sale_invoice(id):
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id,date,due_date,customer_id,product_id,quantity,unit_price,tax_rate,payment_type,status
            FROM sales_invoices
            WHERE id=?
            """,
            (id,),
        )
        invoice = cur.fetchone()
        if not invoice:
            conn.close()
            flash("فاتورة البيع غير موجودة.", "danger")
            return redirect(url_for("sales"))
        if invoice[9] != "draft":
            conn.close()
            flash("لا يمكن تعديل فاتورة مرحلة. فك ترحيل مجموعة فواتير البيع أولا.", "danger")
            return redirect(url_for("sales"))
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            due_date = request.form.get("due_date", "").strip()
            customer_id = request.form.get("customer_id") or None
            product_id = request.form.get("product_id")
            payment_type = request.form.get("payment_type", "cash")
            tax_rate = parse_positive_amount(request.form.get("tax_rate", default_tax_rate))
            quantity = parse_positive_amount(request.form.get("quantity"))
            unit_price = parse_positive_amount(request.form.get("unit_price"))
            cur.execute("SELECT purchase_price FROM products WHERE id=?", (product_id,))
            product = cur.fetchone()
            if not date_value or not product or quantity <= 0 or unit_price <= 0:
                flash("راجع بيانات الفاتورة قبل الحفظ.", "danger")
            elif payment_type == "credit" and not customer_id:
                flash("اختر العميل عند البيع الآجل.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("sales"))
                total = quantity * unit_price
                cost_total = quantity * product[0]
                tax_amount = total * tax_rate / 100
                grand_total = total + tax_amount
                cur.execute(
                    """
                    UPDATE sales_invoices
                    SET date=?,due_date=?,customer_id=?,product_id=?,quantity=?,unit_price=?,total=?,
                        cost_total=?,tax_rate=?,tax_amount=?,grand_total=?,payment_type=?
                    WHERE id=?
                    """,
                    (date_value, due_date, customer_id, product_id, quantity, unit_price, total, cost_total, tax_rate, tax_amount, grand_total, payment_type, id),
                )
                log_action(cur, "update", "sales_invoice", id, "تعديل مسودة")
                conn.commit()
                conn.close()
                flash("تم تعديل فاتورة البيع غير المرحلة.", "success")
                return redirect(url_for("sales"))
        cur.execute("SELECT id,name FROM customers ORDER BY name")
        customers_rows = cur.fetchall()
        cur.execute("SELECT id,name,sale_price,stock_quantity FROM products ORDER BY name")
        product_rows = cur.fetchall()
        conn.close()
        return render_template("edit_sale_invoice.html", invoice=invoice, customers=customers_rows, products=product_rows)

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
        cur.execute("SELECT date,product_id,quantity,journal_id,tax_journal_id,withholding_journal_id,status FROM purchase_invoices WHERE id=?", (id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            flash("فاتورة الشراء غير موجودة.", "danger")
            return redirect(url_for("purchases"))
        date_value, product_id, quantity, journal_id, tax_journal_id, withholding_journal_id, status = row
        if status == "cancelled":
            conn.close()
            flash("فاتورة الشراء ملغاة بالفعل.", "warning")
            return redirect(url_for("purchases"))
        if status == "draft":
            cur.execute("UPDATE purchase_invoices SET status='cancelled', cancelled_at=CURRENT_TIMESTAMP, cancel_reason=? WHERE id=?", (reason, id))
            log_action(cur, "cancel", "purchase_invoice", id, reason)
            conn.commit()
            conn.close()
            flash("تم إلغاء مسودة فاتورة المورد بدون أي أثر محاسبي أو مخزني.", "success")
            return redirect(url_for("purchases"))
        cur.execute("SELECT stock_quantity FROM products WHERE id=?", (product_id,))
        stock = cur.fetchone()[0]
        if stock < quantity:
            conn.close()
            flash("لا يمكن إلغاء فاتورة الشراء لأن رصيد المنتج الحالي لا يكفي لعكس الحركة.", "danger")
            return redirect(url_for("purchases"))
        reverse_journal(cur, journal_id, date_value, reason)
        reverse_journal(cur, tax_journal_id, date_value, reason)
        reverse_journal(cur, withholding_journal_id, date_value, reason)
        cur.execute("UPDATE products SET stock_quantity=stock_quantity-? WHERE id=?", (quantity, product_id))
        cur.execute(
            """
            INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes)
            VALUES (?,?,?,?,?,?,?)
            """,
            (date_value, product_id, "cancel_out", -quantity, "purchase_cancel", id, reason),
        )
        cur.execute("UPDATE purchase_invoices SET status='cancelled', cancelled_at=CURRENT_TIMESTAMP, cancel_reason=? WHERE id=?", (reason, id))
        log_action(cur, "cancel", "purchase_invoice", id, reason)
        conn.commit()
        conn.close()
        rebuild_ledger()
        flash("تم إلغاء فاتورة الشراء وعكس القيود وتحديث المخزون.", "success")
        return redirect(url_for("purchases"))

    return cancel_purchase


def build_edit_purchase_invoice_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    log_action = deps["log_action"]
    default_tax_rate = deps["DEFAULT_TAX_RATE"]

    def edit_purchase_invoice(id):
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id,date,supplier_invoice_no,supplier_invoice_date,due_date,supplier_id,product_id,
                   quantity,unit_price,tax_rate,payment_type,notes,status
            FROM purchase_invoices
            WHERE id=?
            """,
            (id,),
        )
        invoice = cur.fetchone()
        if not invoice:
            conn.close()
            flash("فاتورة المورد غير موجودة.", "danger")
            return redirect(url_for("purchases"))
        if invoice[12] != "draft":
            conn.close()
            flash("لا يمكن تعديل فاتورة مرحلة. فك ترحيل مجموعة فواتير الموردين أولا.", "danger")
            return redirect(url_for("purchases"))
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            supplier_invoice_no = request.form.get("supplier_invoice_no", "").strip()
            supplier_invoice_date = request.form.get("supplier_invoice_date", "").strip()
            due_date = request.form.get("due_date", "").strip()
            supplier_id = request.form.get("supplier_id") or None
            product_id = request.form.get("product_id")
            quantity = parse_positive_amount(request.form.get("quantity"))
            unit_price = parse_positive_amount(request.form.get("unit_price"))
            tax_rate = parse_positive_amount(request.form.get("tax_rate", default_tax_rate))
            payment_type = request.form.get("payment_type", "cash")
            notes = request.form.get("notes", "").strip()
            cur.execute("SELECT 1 FROM products WHERE id=?", (product_id,))
            product = cur.fetchone()
            if not date_value or not supplier_invoice_no or not supplier_invoice_date or not product or quantity <= 0 or unit_price <= 0:
                flash("راجع بيانات فاتورة المورد قبل الحفظ.", "danger")
            elif payment_type == "credit" and not supplier_id:
                flash("اختر المورد عند الشراء الآجل.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("purchases"))
                total = quantity * unit_price
                tax_amount = total * tax_rate / 100
                grand_total = total + tax_amount
                cur.execute(
                    """
                    UPDATE purchase_invoices
                    SET date=?,supplier_invoice_no=?,supplier_invoice_date=?,due_date=?,supplier_id=?,product_id=?,
                        quantity=?,unit_price=?,total=?,tax_rate=?,tax_amount=?,grand_total=?,payment_type=?,notes=?
                    WHERE id=?
                    """,
                    (date_value, supplier_invoice_no, supplier_invoice_date, due_date, supplier_id, product_id, quantity, unit_price, total, tax_rate, tax_amount, grand_total, payment_type, notes, id),
                )
                log_action(cur, "update", "purchase_invoice", id, "تعديل مسودة")
                conn.commit()
                conn.close()
                flash("تم تعديل فاتورة المورد غير المرحلة.", "success")
                return redirect(url_for("purchases"))
        cur.execute("SELECT id,name FROM suppliers ORDER BY name")
        suppliers_rows = cur.fetchall()
        cur.execute("SELECT id,name,purchase_price,stock_quantity FROM products ORDER BY name")
        product_rows = cur.fetchall()
        conn.close()
        return render_template("edit_purchase_invoice.html", invoice=invoice, suppliers=suppliers_rows, products=product_rows)

    return edit_purchase_invoice


def build_cancel_receipt_view(deps):
    db = deps["db"]
    reverse_journal = deps["reverse_journal"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]

    def cancel_receipt(id):
        reason = request.form.get("reason", "").strip() or "إلغاء سند"
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT date,journal_id,status FROM receipt_vouchers WHERE id=?", (id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            flash("سند القبض غير موجود.", "danger")
            return redirect(url_for("receipts"))
        date_value, journal_id, status = row
        if status == "cancelled":
            conn.close()
            flash("سند القبض ملغى بالفعل.", "warning")
            return redirect(url_for("receipts"))
        if status == "draft":
            cur.execute("UPDATE receipt_vouchers SET status='cancelled', cancelled_at=CURRENT_TIMESTAMP, cancel_reason=? WHERE id=?", (reason, id))
            log_action(cur, "cancel", "receipt_voucher", id, reason)
            conn.commit()
            conn.close()
            flash("تم إلغاء مسودة سند القبض بدون أثر محاسبي.", "success")
            return redirect(url_for("receipts"))
        reverse_journal(cur, journal_id, date_value, reason)
        cur.execute("UPDATE receipt_vouchers SET status='cancelled', cancelled_at=CURRENT_TIMESTAMP, cancel_reason=? WHERE id=?", (reason, id))
        log_action(cur, "cancel", "receipt_voucher", id, reason)
        conn.commit()
        conn.close()
        rebuild_ledger()
        flash("تم إلغاء سند القبض وعكس القيد.", "success")
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
            flash("سند القبض غير موجود.", "danger")
            return redirect(url_for("receipts"))
        if voucher[5] != "draft":
            conn.close()
            flash("لا يمكن تعديل سند مرحل. فك ترحيل مجموعة سندات القبض أولا.", "danger")
            return redirect(url_for("receipts"))
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            customer_id = request.form.get("customer_id")
            amount = parse_positive_amount(request.form.get("amount"))
            notes = request.form.get("notes", "").strip()
            if not date_value or not customer_id or amount <= 0:
                flash("راجع بيانات سند القبض.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("receipts"))
                cur.execute("UPDATE receipt_vouchers SET date=?,customer_id=?,amount=?,notes=? WHERE id=?", (date_value, customer_id, amount, notes, id))
                log_action(cur, "update", "receipt_voucher", id, "تعديل مسودة")
                conn.commit()
                conn.close()
                flash("تم تعديل سند القبض غير المرحل.", "success")
                return redirect(url_for("receipts"))
        cur.execute("SELECT id,name FROM customers ORDER BY name")
        customers_rows = cur.fetchall()
        conn.close()
        return render_template("edit_voucher.html", voucher=voucher, parties=customers_rows, party_field="customer_id", title="تعديل سند قبض", back_endpoint="receipts")

    return edit_receipt


def build_cancel_payment_view(deps):
    db = deps["db"]
    reverse_journal = deps["reverse_journal"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]

    def cancel_payment(id):
        reason = request.form.get("reason", "").strip() or "إلغاء سند"
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT date,journal_id,status FROM payment_vouchers WHERE id=?", (id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            flash("سند الصرف غير موجود.", "danger")
            return redirect(url_for("payments"))
        date_value, journal_id, status = row
        if status == "cancelled":
            conn.close()
            flash("سند الصرف ملغى بالفعل.", "warning")
            return redirect(url_for("payments"))
        if status == "draft":
            cur.execute("UPDATE payment_vouchers SET status='cancelled', cancelled_at=CURRENT_TIMESTAMP, cancel_reason=? WHERE id=?", (reason, id))
            log_action(cur, "cancel", "payment_voucher", id, reason)
            conn.commit()
            conn.close()
            flash("تم إلغاء مسودة سند الصرف بدون أثر محاسبي.", "success")
            return redirect(url_for("payments"))
        reverse_journal(cur, journal_id, date_value, reason)
        cur.execute("UPDATE payment_vouchers SET status='cancelled', cancelled_at=CURRENT_TIMESTAMP, cancel_reason=? WHERE id=?", (reason, id))
        log_action(cur, "cancel", "payment_voucher", id, reason)
        conn.commit()
        conn.close()
        rebuild_ledger()
        flash("تم إلغاء سند الصرف وعكس القيد.", "success")
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
            flash("سند الصرف غير موجود.", "danger")
            return redirect(url_for("payments"))
        if voucher[5] != "draft":
            conn.close()
            flash("لا يمكن تعديل سند مرحل. فك ترحيل مجموعة سندات الصرف أولا.", "danger")
            return redirect(url_for("payments"))
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            supplier_id = request.form.get("supplier_id")
            amount = parse_positive_amount(request.form.get("amount"))
            notes = request.form.get("notes", "").strip()
            if not date_value or not supplier_id or amount <= 0:
                flash("راجع بيانات سند الصرف.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("payments"))
                cur.execute("UPDATE payment_vouchers SET date=?,supplier_id=?,amount=?,notes=? WHERE id=?", (date_value, supplier_id, amount, notes, id))
                log_action(cur, "update", "payment_voucher", id, "تعديل مسودة")
                conn.commit()
                conn.close()
                flash("تم تعديل سند الصرف غير المرحل.", "success")
                return redirect(url_for("payments"))
        cur.execute("SELECT id,name FROM suppliers ORDER BY name")
        suppliers_rows = cur.fetchall()
        conn.close()
        return render_template("edit_voucher.html", voucher=voucher, parties=suppliers_rows, party_field="supplier_id", title="تعديل سند صرف", back_endpoint="payments")

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
                flash("راجع بيانات التخصيص.", "danger")
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
                    flash("الفاتورة أو السند غير موجود أو غير مرحل.", "danger")
                elif invoice[1] != voucher[1]:
                    flash("لا يمكن ربط سند بطرف مختلف عن طرف الفاتورة.", "danger")
                else:
                    cur.execute("SELECT COALESCE(SUM(amount),0) FROM invoice_allocations WHERE allocation_type=? AND invoice_id=?", (allocation_type, invoice_id))
                    allocated_invoice = cur.fetchone()[0]
                    cur.execute("SELECT COALESCE(SUM(amount),0) FROM invoice_allocations WHERE allocation_type=? AND voucher_id=?", (allocation_type, voucher_id))
                    allocated_voucher = cur.fetchone()[0]
                    if allocated_invoice + amount > invoice[0]:
                        flash("مبلغ الربط أكبر من المتبقي على الفاتورة.", "danger")
                    elif allocated_voucher + amount > voucher[0]:
                        flash("مبلغ الربط أكبر من المتبقي في السند.", "danger")
                    else:
                        cur.execute("INSERT INTO invoice_allocations(allocation_type,invoice_id,voucher_id,amount) VALUES (?,?,?,?)", (allocation_type, invoice_id, voucher_id, amount))
                        allocation_id = cur.lastrowid
                        log_action(cur, "create", "invoice_allocation", allocation_id, f"{allocation_type}:{amount}")
                        conn.commit()
                        flash("تم ربط السداد/التحصيل بالفاتورة.", "success")
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
