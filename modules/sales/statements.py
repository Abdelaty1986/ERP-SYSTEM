from flask import flash, redirect, render_template, request, url_for


def _render_party_statement(
    *,
    company,
    title,
    party_name,
    party_type,
    entries,
    balance_mode="debit_minus_credit",
):
    entries.sort(key=lambda row: (row[0], row[1]))
    debit = sum(row[2] for row in entries)
    credit = sum(row[3] for row in entries)
    balance = debit - credit if balance_mode == "debit_minus_credit" else credit - debit
    return render_template(
        "party_statement.html",
        title=title,
        company=company,
        party_name=party_name,
        party_type=party_type,
        rows=entries,
        debit=debit,
        credit=credit,
        balance=balance,
        balance_label="مدين" if balance > 0 and balance_mode == "debit_minus_credit" else "دائن" if balance > 0 else "متوازن",
    )


def _build_customer_official_entries(cur, customer_id):
    entries = []

    # كشف الحساب الرسمي: الآجل فقط + التحصيلات + التسويات.
    cur.execute(
        """
        SELECT date,id,(grand_total - COALESCE(withholding_amount,0)),status,cancel_reason
        FROM sales_invoices
        WHERE customer_id=? AND status<>'draft' AND payment_type='credit'
        ORDER BY id
        """,
        (customer_id,),
    )
    for date_value, invoice_id, total, status, cancel_reason in cur.fetchall():
        display_status = "ملغى" if status == "cancelled" else "مرحل"
        suffix = f" - سبب الإلغاء: {cancel_reason}" if status == "cancelled" and cancel_reason else ""
        entries.append((date_value, f"فاتورة بيع آجلة #{invoice_id}{suffix}", total, 0, display_status))
        if status == "cancelled":
            entries.append((date_value, f"إلغاء فاتورة بيع آجلة #{invoice_id}", 0, total, "إلغاء"))

    cur.execute(
        """
        SELECT sr.date,sr.id,sr.grand_total,p.name
        FROM sales_returns sr
        JOIN sales_invoices si ON si.id=sr.sales_invoice_id
        JOIN products p ON p.id=sr.product_id
        WHERE si.customer_id=? AND si.payment_type='credit'
        ORDER BY sr.id
        """,
        (customer_id,),
    )
    for date_value, return_id, total, product_name in cur.fetchall():
        entries.append((date_value, f"مردود مبيعات #{return_id} - {product_name}", 0, total, "مرحل"))

    cur.execute(
        """
        SELECT date,doc_no,adjustment_type,description,grand_total,status
        FROM customer_adjustments
        WHERE customer_id=? AND status<>'draft'
        ORDER BY id
        """,
        (customer_id,),
    )
    for date_value, doc_no, adjustment_type, description, total, status in cur.fetchall():
        display_status = "ملغى" if status == "cancelled" else "مرحل"
        if adjustment_type == "debit":
            entries.append((date_value, f"تسوية مدينة {doc_no} - {description}", total, 0, display_status))
        else:
            entries.append((date_value, f"تسوية دائنة {doc_no} - {description}", 0, total, display_status))

    cur.execute(
        """
        SELECT date,id,amount,notes,status,cancel_reason
        FROM receipt_vouchers
        WHERE customer_id=? AND status<>'draft'
        ORDER BY id
        """,
        (customer_id,),
    )
    for date_value, voucher_id, amount, notes, status, cancel_reason in cur.fetchall():
        display_status = "ملغى" if status == "cancelled" else "مرحل"
        label = f"سند قبض #{voucher_id}"
        if notes:
            label += f" - {notes}"
        if status == "cancelled" and cancel_reason:
            label += f" - سبب الإلغاء: {cancel_reason}"
        entries.append((date_value, label, 0, amount, display_status))
        if status == "cancelled":
            entries.append((date_value, f"إلغاء سند قبض #{voucher_id}", amount, 0, "إلغاء"))

    return entries


def _build_customer_transaction_entries(cur, customer_id):
    entries = []

    # تقرير التعاملات: يعرض كل الحركات النقدية والآجلة لغرض المتابعة التجارية، وليس كرصيد رسمي.
    cur.execute(
        """
        SELECT date,id,(grand_total - COALESCE(withholding_amount,0)),payment_type,status,cancel_reason
        FROM sales_invoices
        WHERE customer_id=? AND status<>'draft'
        ORDER BY id
        """,
        (customer_id,),
    )
    for date_value, invoice_id, total, payment_type, status, cancel_reason in cur.fetchall():
        display_status = "ملغى" if status == "cancelled" else "مرحل"
        suffix = f" - سبب الإلغاء: {cancel_reason}" if status == "cancelled" and cancel_reason else ""
        if payment_type == "credit":
            entries.append((date_value, f"فاتورة بيع آجلة #{invoice_id}{suffix}", total, 0, display_status))
            if status == "cancelled":
                entries.append((date_value, f"إلغاء فاتورة بيع آجلة #{invoice_id}", 0, total, "إلغاء"))
        else:
            entries.append((date_value, f"فاتورة بيع نقدية #{invoice_id}{suffix}", total, 0, display_status))
            entries.append((date_value, f"تحصيل نقدي لفاتورة #{invoice_id}{suffix}", 0, total, display_status))

    cur.execute(
        """
        SELECT sr.date,sr.id,sr.grand_total,si.payment_type,p.name
        FROM sales_returns sr
        JOIN sales_invoices si ON si.id=sr.sales_invoice_id
        JOIN products p ON p.id=sr.product_id
        WHERE si.customer_id=?
        ORDER BY sr.id
        """,
        (customer_id,),
    )
    for date_value, return_id, total, payment_type, product_name in cur.fetchall():
        if payment_type == "credit":
            entries.append((date_value, f"مردود مبيعات #{return_id} - {product_name}", 0, total, "مرحل"))
        else:
            entries.append((date_value, f"مردود مبيعات نقدي #{return_id} - {product_name}", 0, total, "مرحل"))
            entries.append((date_value, f"رد نقدية عن مردود #{return_id}", total, 0, "مرحل"))

    entries.extend(_build_customer_official_entries(cur, customer_id))

    # إزالة التكرار الناتج عن إضافة الآجل في التقرير الرسمي والتعاملات.
    unique = []
    seen = set()
    for row in entries:
        key = tuple(row)
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


def build_customer_statement_view(deps):
    db = deps["db"]
    get_company_settings = deps["get_company_settings"]

    def customer_statement(id):
        conn = db()
        cur = conn.cursor()
        company = get_company_settings(cur)
        cur.execute("SELECT name FROM customers WHERE id=?", (id,))
        customer = cur.fetchone()
        if not customer:
            conn.close()
            flash("العميل غير موجود.", "danger")
            return redirect(url_for("customers"))

        mode = (request.args.get("mode") or "official").strip().lower()
        if mode == "transactions":
            entries = _build_customer_transaction_entries(cur, id)
            title = f"تقرير تعاملات العميل: {customer[0]}"
        else:
            entries = _build_customer_official_entries(cur, id)
            title = f"كشف حساب العميل: {customer[0]}"

        conn.close()
        return _render_party_statement(
            company=company,
            title=title,
            party_name=customer[0],
            party_type="عميل",
            entries=entries,
            balance_mode="debit_minus_credit",
        )

    return customer_statement


def _build_supplier_official_entries(cur, supplier_id):
    entries = []

    cur.execute(
        """
        SELECT date,id,(grand_total - COALESCE(withholding_amount,0)),status,cancel_reason
        FROM purchase_invoices
        WHERE supplier_id=? AND status<>'draft' AND payment_type='credit'
        ORDER BY id
        """,
        (supplier_id,),
    )
    for date_value, invoice_id, total, status, cancel_reason in cur.fetchall():
        display_status = "ملغى" if status == "cancelled" else "مرحل"
        suffix = f" - سبب الإلغاء: {cancel_reason}" if status == "cancelled" and cancel_reason else ""
        entries.append((date_value, f"فاتورة شراء آجلة #{invoice_id}{suffix}", 0, total, display_status))
        if status == "cancelled":
            entries.append((date_value, f"إلغاء فاتورة شراء آجلة #{invoice_id}", total, 0, "إلغاء"))

    cur.execute(
        """
        SELECT pr.date,pr.id,pr.grand_total,p.name
        FROM purchase_returns pr
        JOIN purchase_invoices pi ON pi.id=pr.purchase_invoice_id
        JOIN products p ON p.id=pr.product_id
        WHERE pi.supplier_id=? AND pi.payment_type='credit'
        ORDER BY pr.id
        """,
        (supplier_id,),
    )
    for date_value, return_id, total, product_name in cur.fetchall():
        entries.append((date_value, f"مردود مشتريات #{return_id} - {product_name}", total, 0, "مرحل"))

    cur.execute(
        """
        SELECT date,id,amount,notes,status,cancel_reason
        FROM payment_vouchers
        WHERE supplier_id=? AND status<>'draft'
        ORDER BY id
        """,
        (supplier_id,),
    )
    for date_value, voucher_id, amount, notes, status, cancel_reason in cur.fetchall():
        display_status = "ملغى" if status == "cancelled" else "مرحل"
        label = f"سند صرف #{voucher_id}"
        if notes:
            label += f" - {notes}"
        if status == "cancelled" and cancel_reason:
            label += f" - سبب الإلغاء: {cancel_reason}"
        entries.append((date_value, label, amount, 0, display_status))
        if status == "cancelled":
            entries.append((date_value, f"إلغاء سند صرف #{voucher_id}", 0, amount, "إلغاء"))

    return entries


def _build_supplier_transaction_entries(cur, supplier_id):
    entries = []

    cur.execute(
        """
        SELECT date,id,(grand_total - COALESCE(withholding_amount,0)),payment_type,status,cancel_reason
        FROM purchase_invoices
        WHERE supplier_id=? AND status<>'draft'
        ORDER BY id
        """,
        (supplier_id,),
    )
    for date_value, invoice_id, total, payment_type, status, cancel_reason in cur.fetchall():
        display_status = "ملغى" if status == "cancelled" else "مرحل"
        suffix = f" - سبب الإلغاء: {cancel_reason}" if status == "cancelled" and cancel_reason else ""
        if payment_type == "credit":
            entries.append((date_value, f"فاتورة شراء آجلة #{invoice_id}{suffix}", 0, total, display_status))
            if status == "cancelled":
                entries.append((date_value, f"إلغاء فاتورة شراء آجلة #{invoice_id}", total, 0, "إلغاء"))
        else:
            entries.append((date_value, f"فاتورة شراء نقدية #{invoice_id}{suffix}", 0, total, display_status))
            entries.append((date_value, f"سداد نقدي لفاتورة #{invoice_id}{suffix}", total, 0, display_status))

    cur.execute(
        """
        SELECT pr.date,pr.id,pr.grand_total,pi.payment_type,p.name
        FROM purchase_returns pr
        JOIN purchase_invoices pi ON pi.id=pr.purchase_invoice_id
        JOIN products p ON p.id=pr.product_id
        WHERE pi.supplier_id=?
        ORDER BY pr.id
        """,
        (supplier_id,),
    )
    for date_value, return_id, total, payment_type, product_name in cur.fetchall():
        if payment_type == "credit":
            entries.append((date_value, f"مردود مشتريات #{return_id} - {product_name}", total, 0, "مرحل"))
        else:
            entries.append((date_value, f"مردود مشتريات نقدي #{return_id} - {product_name}", total, 0, "مرحل"))
            entries.append((date_value, f"استرداد نقدية عن مردود #{return_id}", 0, total, "مرحل"))

    entries.extend(_build_supplier_official_entries(cur, supplier_id))

    unique = []
    seen = set()
    for row in entries:
        key = tuple(row)
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


def build_supplier_statement_view(deps):
    db = deps["db"]
    get_company_settings = deps["get_company_settings"]

    def supplier_statement(id):
        conn = db()
        cur = conn.cursor()
        company = get_company_settings(cur)
        cur.execute("SELECT name FROM suppliers WHERE id=?", (id,))
        supplier = cur.fetchone()
        if not supplier:
            conn.close()
            flash("المورد غير موجود.", "danger")
            return redirect(url_for("suppliers"))

        mode = (request.args.get("mode") or "official").strip().lower()
        if mode == "transactions":
            entries = _build_supplier_transaction_entries(cur, id)
            title = f"تقرير تعاملات المورد: {supplier[0]}"
        else:
            entries = _build_supplier_official_entries(cur, id)
            title = f"كشف حساب المورد: {supplier[0]}"

        conn.close()
        return _render_party_statement(
            company=company,
            title=title,
            party_name=supplier[0],
            party_type="مورد",
            entries=entries,
            balance_mode="credit_minus_debit",
        )

    return supplier_statement
