from flask import flash, redirect, render_template, url_for


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

        entries = []
        cur.execute("SELECT date,id,(grand_total - COALESCE(withholding_amount,0)),payment_type,status,cancel_reason FROM sales_invoices WHERE customer_id=? AND status<>'draft'", (id,))
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
            (id,),
        )
        for date_value, return_id, total, payment_type, product_name in cur.fetchall():
            if payment_type == "credit":
                entries.append((date_value, f"مردود مبيعات #{return_id} - {product_name}", 0, total, "مرحل"))
            else:
                entries.append((date_value, f"مردود مبيعات نقدي #{return_id} - {product_name}", 0, total, "مرحل"))
                entries.append((date_value, f"رد نقدية عن مردود #{return_id}", total, 0, "مرحل"))

        cur.execute(
            """
            SELECT date,doc_no,adjustment_type,description,grand_total,status
            FROM customer_adjustments
            WHERE customer_id=? AND status<>'draft'
            ORDER BY id
            """,
            (id,),
        )
        for date_value, doc_no, adjustment_type, description, total, status in cur.fetchall():
            display_status = "ملغى" if status == "cancelled" else "مرحل"
            if adjustment_type == "debit":
                entries.append((date_value, f"تسوية مدينة {doc_no} - {description}", total, 0, display_status))
            else:
                entries.append((date_value, f"تسوية دائنة {doc_no} - {description}", 0, total, display_status))

        cur.execute("SELECT date,id,amount,notes,status,cancel_reason FROM receipt_vouchers WHERE customer_id=? AND status<>'draft'", (id,))
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

        entries.sort(key=lambda row: (row[0], row[1]))
        debit = sum(row[2] for row in entries)
        credit = sum(row[3] for row in entries)
        balance = debit - credit
        conn.close()
        return render_template(
            "party_statement.html",
            title=f"كشف حساب العميل: {customer[0]}",
            company=company,
            party_name=customer[0],
            party_type="عميل",
            rows=entries,
            debit=debit,
            credit=credit,
            balance=balance,
            balance_label="مدين" if balance > 0 else "دائن",
        )

    return customer_statement


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
        entries = []
        cur.execute("SELECT date,id,(grand_total - COALESCE(withholding_amount,0)),payment_type,status,cancel_reason FROM purchase_invoices WHERE supplier_id=? AND status<>'draft'", (id,))
        for date_value, invoice_id, total, payment_type, status, cancel_reason in cur.fetchall():
            display_status = "ملغى" if status == "cancelled" else "مرحل"
            suffix = f" - سبب الإلغاء: {cancel_reason}" if status == "cancelled" and cancel_reason else ""
            if payment_type == "credit":
                entries.append((date_value, f"فاتورة شراء آجلة #{invoice_id}{suffix}", 0, total, display_status))
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
            (id,),
        )
        for date_value, return_id, total, payment_type, product_name in cur.fetchall():
            if payment_type == "credit":
                entries.append((date_value, f"مردود مشتريات #{return_id} - {product_name}", total, 0, "مرحل"))
            else:
                entries.append((date_value, f"مردود مشتريات نقدي #{return_id} - {product_name}", total, 0, "مرحل"))
                entries.append((date_value, f"استرداد نقدية عن مردود #{return_id}", 0, total, "مرحل"))
        cur.execute("SELECT date,id,amount,notes,status,cancel_reason FROM payment_vouchers WHERE supplier_id=? AND status<>'draft'", (id,))
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
        entries.sort(key=lambda row: row[0])
        debit = sum(row[2] for row in entries)
        credit = sum(row[3] for row in entries)
        balance = credit - debit
        conn.close()
        return render_template(
            "party_statement.html",
            title=f"كشف حساب المورد: {supplier[0]}",
            company=company,
            party_name=supplier[0],
            party_type="مورد",
            rows=entries,
            debit=debit,
            credit=credit,
            balance=balance,
            balance_label="دائن" if balance > 0 else "مدين",
        )

    return supplier_statement
