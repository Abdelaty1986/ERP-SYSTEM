from flask import flash, redirect, render_template, request, url_for


def build_receipts_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]
    is_group_posted = deps["is_group_posted"]

    def receipts():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            customer_id = request.form.get("customer_id")
            amount = parse_positive_amount(request.form.get("amount"))
            notes = request.form.get("notes", "").strip()
            cur.execute("SELECT name FROM customers WHERE id=?", (customer_id,))
            customer = cur.fetchone()
            if not date_value:
                flash("التاريخ مطلوب.", "danger")
            elif not customer:
                flash("العميل غير موجود.", "danger")
            elif amount <= 0:
                flash("المبلغ يجب أن يكون أكبر من صفر.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("receipts"))
                group_posted = is_group_posted(cur, "receipts")
                journal_id = create_auto_journal(cur, date_value, f"سند قبض من {customer[0]}", "1100", "1300", amount) if group_posted else None
                cur.execute(
                    "INSERT INTO receipt_vouchers(date,customer_id,amount,notes,journal_id,status) VALUES (?,?,?,?,?,?)",
                    (date_value, customer_id, amount, notes, journal_id, "posted" if group_posted else "draft"),
                )
                voucher_id = cur.lastrowid
                mark_journal_source(cur, "receipts", voucher_id, journal_id)
                log_action(cur, "create", "receipt_voucher", voucher_id, f"amount={amount}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash("تم حفظ سند القبض." + (" تم ترحيله." if group_posted else " محفوظ كمسودة غير مرحلة."), "success")
                return redirect(url_for("receipts"))
        cur.execute("SELECT id,name FROM customers ORDER BY name")
        customers_rows = cur.fetchall()
        cur.execute(
            """
            SELECT r.id,r.date,c.name,r.amount,r.notes,r.status,r.cancel_reason
            FROM receipt_vouchers r
            JOIN customers c ON r.customer_id=c.id
            ORDER BY r.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("receipts.html", customers=customers_rows, rows=rows)

    return receipts


def build_payments_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]
    is_group_posted = deps["is_group_posted"]

    def payments():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            supplier_id = request.form.get("supplier_id")
            amount = parse_positive_amount(request.form.get("amount"))
            notes = request.form.get("notes", "").strip()
            cur.execute("SELECT name FROM suppliers WHERE id=?", (supplier_id,))
            supplier = cur.fetchone()
            if not date_value:
                flash("التاريخ مطلوب.", "danger")
            elif not supplier:
                flash("المورد غير موجود.", "danger")
            elif amount <= 0:
                flash("المبلغ يجب أن يكون أكبر من صفر.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("payments"))
                group_posted = is_group_posted(cur, "payments")
                journal_id = create_auto_journal(cur, date_value, f"سند صرف إلى {supplier[0]}", "2100", "1100", amount) if group_posted else None
                cur.execute(
                    "INSERT INTO payment_vouchers(date,supplier_id,amount,notes,journal_id,status) VALUES (?,?,?,?,?,?)",
                    (date_value, supplier_id, amount, notes, journal_id, "posted" if group_posted else "draft"),
                )
                voucher_id = cur.lastrowid
                mark_journal_source(cur, "payments", voucher_id, journal_id)
                log_action(cur, "create", "payment_voucher", voucher_id, f"amount={amount}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash("تم حفظ سند الصرف." + (" تم ترحيله." if group_posted else " محفوظ كمسودة غير مرحلة."), "success")
                return redirect(url_for("payments"))
        cur.execute("SELECT id,name FROM suppliers ORDER BY name")
        suppliers_rows = cur.fetchall()
        cur.execute(
            """
            SELECT p.id,p.date,s.name,p.amount,p.notes,p.status,p.cancel_reason
            FROM payment_vouchers p
            JOIN suppliers s ON p.supplier_id=s.id
            ORDER BY p.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("payments.html", suppliers=suppliers_rows, rows=rows)

    return payments


def build_print_receipt_view(deps):
    db = deps["db"]
    get_company_settings = deps["get_company_settings"]
    amount_to_words = deps["amount_to_words"]

    def print_receipt(id):
        conn = db()
        cur = conn.cursor()
        company = get_company_settings(cur)
        cur.execute(
            """
            SELECT r.id,r.date,c.name,COALESCE(c.phone,''),COALESCE(c.address,''),
                   r.amount,r.notes,r.status,r.cancel_reason
            FROM receipt_vouchers r
            JOIN customers c ON r.customer_id=c.id
            WHERE r.id=?
            """,
            (id,),
        )
        doc = cur.fetchone()
        conn.close()
        if not doc:
            flash("سند القبض غير موجود.", "danger")
            return redirect(url_for("receipts"))
        return render_template("print_voucher.html", company=company, doc=doc, doc_type="سند قبض", party_label="العميل", amount_in_words=amount_to_words(doc[5]))

    return print_receipt


def build_print_payment_view(deps):
    db = deps["db"]
    get_company_settings = deps["get_company_settings"]
    amount_to_words = deps["amount_to_words"]

    def print_payment(id):
        conn = db()
        cur = conn.cursor()
        company = get_company_settings(cur)
        cur.execute(
            """
            SELECT p.id,p.date,s.name,COALESCE(s.phone,''),COALESCE(s.address,''),
                   p.amount,p.notes,p.status,p.cancel_reason
            FROM payment_vouchers p
            JOIN suppliers s ON p.supplier_id=s.id
            WHERE p.id=?
            """,
            (id,),
        )
        doc = cur.fetchone()
        conn.close()
        if not doc:
            flash("سند الصرف غير موجود.", "danger")
            return redirect(url_for("payments"))
        return render_template("print_voucher.html", company=company, doc=doc, doc_type="سند صرف", party_label="المورد", amount_in_words=amount_to_words(doc[5]))

    return print_payment


def build_customer_adjustments_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]
    next_document_number = deps["next_document_number"]
    is_group_posted = deps["is_group_posted"]

    def customer_adjustments():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            customer_id = int(parse_positive_amount(request.form.get("customer_id")) or 0)
            related_invoice_id = int(parse_positive_amount(request.form.get("related_invoice_id")) or 0) or None
            adjustment_type = request.form.get("adjustment_type", "").strip()
            description = request.form.get("description", "").strip()
            total = parse_positive_amount(request.form.get("total"))
            tax_rate = parse_positive_amount(request.form.get("tax_rate"))
            notes = request.form.get("notes", "").strip()
            tax_amount = total * tax_rate / 100
            grand_total = total + tax_amount
            cur.execute("SELECT name FROM customers WHERE id=?", (customer_id,))
            customer = cur.fetchone()
            if not date_value:
                flash("تاريخ التسوية مطلوب.", "danger")
            elif adjustment_type not in ("debit", "credit"):
                flash("نوع التسوية غير صحيح.", "danger")
            elif not customer:
                flash("العميل غير موجود.", "danger")
            elif not description:
                flash("وصف التسوية مطلوب.", "danger")
            elif total <= 0:
                flash("مبلغ التسوية يجب أن يكون أكبر من صفر.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("customer_adjustments"))
                group_posted = is_group_posted(cur, "sales")
                journal_id = None
                tax_journal_id = None
                if group_posted:
                    if adjustment_type == "debit":
                        journal_id = create_auto_journal(cur, date_value, f"تسوية مدينة للعميل {customer[0]} - {description}", "1300", "4400", total)
                        if tax_amount > 0:
                            tax_journal_id = create_auto_journal(cur, date_value, f"ضريبة تسوية مدينة للعميل {customer[0]}", "1300", "2200", tax_amount)
                    else:
                        journal_id = create_auto_journal(cur, date_value, f"تسوية دائنة للعميل {customer[0]} - {description}", "4200", "1300", total)
                        if tax_amount > 0:
                            tax_journal_id = create_auto_journal(cur, date_value, f"ضريبة تسوية دائنة للعميل {customer[0]}", "2200", "1300", tax_amount)
                doc_no = next_document_number(cur, "customer_adjustments")
                cur.execute(
                    """
                    INSERT INTO customer_adjustments(
                        date,doc_no,customer_id,adjustment_type,related_invoice_id,description,total,tax_rate,tax_amount,grand_total,journal_id,tax_journal_id,status,notes
                    )
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (date_value, doc_no, customer_id, adjustment_type, related_invoice_id, description, total, tax_rate, tax_amount, grand_total, journal_id, tax_journal_id, "posted" if group_posted else "draft", notes),
                )
                adjustment_id = cur.lastrowid
                mark_journal_source(cur, "customer_adjustment", adjustment_id, journal_id, tax_journal_id)
                log_action(cur, "create", "customer_adjustment", adjustment_id, f"{doc_no}; type={adjustment_type}; total={grand_total}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash(f"تم تسجيل التسوية {doc_no}.", "success")
                return redirect(url_for("customer_adjustments"))
        cur.execute("SELECT id,name FROM customers ORDER BY name")
        customers_rows = cur.fetchall()
        cur.execute("SELECT id,doc_no,date,grand_total FROM sales_invoices WHERE status='posted' ORDER BY id DESC")
        invoices = cur.fetchall()
        cur.execute(
            """
            SELECT a.id,a.date,a.doc_no,c.name,a.adjustment_type,a.description,a.grand_total,a.status
            FROM customer_adjustments a
            JOIN customers c ON c.id=a.customer_id
            ORDER BY a.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("customer_adjustments.html", customers=customers_rows, invoices=invoices, rows=rows)

    return customer_adjustments


def build_print_customer_adjustment_view(deps):
    db = deps["db"]
    get_company_settings = deps["get_company_settings"]
    amount_to_words = deps["amount_to_words"]

    def print_customer_adjustment(id):
        conn = db()
        cur = conn.cursor()
        company = get_company_settings(cur)
        cur.execute(
            """
            SELECT a.id,a.date,a.doc_no,c.name,COALESCE(c.phone,''),COALESCE(c.address,''),
                   a.description,a.total,a.tax_rate,a.tax_amount,a.grand_total,a.notes,a.adjustment_type,COALESCE(s.doc_no,'')
            FROM customer_adjustments a
            JOIN customers c ON c.id=a.customer_id
            LEFT JOIN sales_invoices s ON s.id=a.related_invoice_id
            WHERE a.id=?
            """,
            (id,),
        )
        doc = cur.fetchone()
        conn.close()
        if not doc:
            flash("التسوية غير موجودة.", "danger")
            return redirect(url_for("customer_adjustments"))
        return render_template(
            "print_customer_note.html",
            company=company,
            doc=doc,
            doc_title="تسوية عميل",
            note_kind=doc[12],
            party_label="العميل",
            amount_in_words=amount_to_words(doc[10]),
            source_label=f"مرجع الفاتورة: {doc[13]}" if doc[13] else "",
        )

    return print_customer_adjustment


def build_prepare_customer_adjustment_einvoice_view(deps):
    db = deps["db"]
    prepare_einvoice_document = deps["prepare_einvoice_document"]
    log_action = deps["log_action"]

    def prepare_customer_adjustment_einvoice(id):
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT adjustment_type FROM customer_adjustments WHERE id=?", (id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            flash("التسوية غير موجودة.", "danger")
            return redirect(url_for("customer_adjustments"))
        doc_type = "customer_debit_note" if row[0] == "debit" else "customer_credit_note"
        _, created = prepare_einvoice_document(cur, doc_type, id)
        log_action(cur, "prepare", "e_invoice_documents", None, f"{doc_type}={id}")
        conn.commit()
        conn.close()
        flash("تم تجهيز التسوية للرفع على بوابة الضرائب." if created else "هذه التسوية مجهزة بالفعل للرفع.", "success")
        return redirect(url_for("customer_adjustments"))

    return prepare_customer_adjustment_einvoice
