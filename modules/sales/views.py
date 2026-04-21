import json

from flask import flash, redirect, render_template, request, url_for
from modules.sales.advanced import (
    build_financial_sales_view,
    build_purchase_invoice_from_receipt_view,
    build_sales_invoice_from_delivery_view,
)
from modules.sales.documents import (
    build_prepare_sales_credit_note_einvoice_view,
    build_print_purchase_view,
    build_print_sale_view,
    build_print_sales_credit_note_view,
)
from modules.sales.orders import (
    build_print_purchase_order_view,
    build_purchase_orders_view,
    build_sales_orders_view,
)
from modules.sales.shipping import (
    build_purchase_receipts_view,
    build_sales_deliveries_view,
)
from modules.sales.returns import (
    build_purchase_returns_view,
    build_sales_credit_notes_view,
    build_sales_returns_view,
)
from modules.sales.statements import build_customer_statement_view, build_supplier_statement_view
from modules.sales.treasury import (
    build_customer_adjustments_view,
    build_payments_view,
    build_prepare_customer_adjustment_einvoice_view,
    build_print_customer_adjustment_view,
    build_print_payment_view,
    build_print_receipt_view,
    build_receipts_view,
)


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
                       COALESCE((SELECT SUM(quantity) FROM purchase_returns rr WHERE rr.purchase_invoice_id=p.id AND rr.product_id=p.product_id),0)
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
    return invoice_id, result


def _customer_withholding(cur, customer_id):
    if not customer_id:
        return "non_subject", 0
    cur.execute("SELECT withholding_status FROM customers WHERE id=?", (customer_id,))
    row = cur.fetchone()
    status = (row[0] if row else "non_subject") or "non_subject"
    return status, (1 if status == "subject" else 0)


def _supplier_withholding(cur, supplier_id):
    if not supplier_id:
        return "exempt", 0
    cur.execute("SELECT withholding_status FROM suppliers WHERE id=?", (supplier_id,))
    row = cur.fetchone()
    status = (row[0] if row else "exempt") or "exempt"
    return status, (1 if status == "taxable" else 0)


def _legacy_build_customer_statement_view(deps):
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

        cur.execute("SELECT date,id,grand_total,payment_type,status,cancel_reason FROM sales_invoices WHERE customer_id=? AND status<>'draft'", (id,))
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


def _legacy_build_supplier_statement_view(deps):
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
        cur.execute("SELECT date,id,grand_total,payment_type,status,cancel_reason FROM purchase_invoices WHERE supplier_id=? AND status<>'draft'", (id,))
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


def _legacy_build_print_sale_view(deps):
    db = deps["db"]
    get_company_settings = deps["get_company_settings"]
    amount_to_words = deps["amount_to_words"]

    def print_sale(id):
        conn = db()
        cur = conn.cursor()
        company = get_company_settings(cur)
        cur.execute(
            """
            SELECT s.id,s.date,COALESCE(c.name,'بيع نقدي'),COALESCE(c.phone,''),COALESCE(c.address,''),
                   p.name,p.unit,s.quantity,s.unit_price,s.total,s.tax_rate,s.tax_amount,s.grand_total,
                   s.payment_type,s.status,s.cancel_reason,s.due_date
            FROM sales_invoices s
            LEFT JOIN customers c ON s.customer_id=c.id
            JOIN products p ON s.product_id=p.id
            WHERE s.id=?
            """,
            (id,),
        )
        doc = cur.fetchone()
        conn.close()
        if not doc:
            flash("فاتورة البيع غير موجودة.", "danger")
            return redirect(url_for("sales"))
        return render_template(
            "print_document.html",
            company=company,
            doc=doc,
            doc_type="فاتورة بيع",
            party_label="العميل",
            sales_invoice=True,
            amount_in_words=amount_to_words(doc[12]),
        )

    return print_sale


def build_sales_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]
    next_document_number = deps["next_document_number"]
    default_tax_rate = deps["DEFAULT_TAX_RATE"]
    is_group_posted = deps["is_group_posted"]

    def sales():
        conn = db()
        cur = conn.cursor()

        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            due_date = request.form.get("due_date", "").strip()
            customer_id = request.form.get("customer_id") or None
            product_id = request.form.get("product_id")
            payment_type = request.form.get("payment_type", "cash")
            tax_rate = parse_positive_amount(request.form.get("tax_rate", default_tax_rate))
            po_ref = request.form.get("po_ref", "").strip()
            gr_ref = request.form.get("gr_ref", "").strip()
            notes = request.form.get("notes", "").strip()

            try:
                quantity = float(request.form.get("quantity", 0) or 0)
                unit_price = float(request.form.get("unit_price", 0) or 0)
            except ValueError:
                quantity = 0
                unit_price = 0
                flash("الكمية والسعر يجب أن يكونا أرقاما.", "danger")

            cur.execute("SELECT name, stock_quantity, purchase_price FROM products WHERE id=?", (product_id,))
            product = cur.fetchone()
            _, withholding_rate = _customer_withholding(cur, customer_id)

            if not date_value:
                flash("التاريخ مطلوب.", "danger")
            elif not product:
                flash("المنتج غير موجود.", "danger")
            elif payment_type == "credit" and not customer_id:
                flash("اختر العميل عند البيع الآجل.", "danger")
            elif quantity <= 0 or unit_price <= 0:
                flash("الكمية والسعر يجب أن يكونا أكبر من صفر.", "danger")
            elif tax_rate < 0:
                flash("نسبة الضريبة لا يمكن أن تكون سالبة.", "danger")
            elif product[1] < quantity:
                flash("الرصيد المتاح من المنتج لا يكفي لإتمام البيع.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("sales"))
                total = quantity * unit_price
                cost_total = quantity * product[2]
                tax_amount = total * tax_rate / 100
                grand_total = total + tax_amount
                withholding_amount = round(grand_total * withholding_rate / 100, 2)
                debit_code = "1300" if payment_type == "credit" else "1100"
                group_posted = is_group_posted(cur, "sales")
                doc_no = next_document_number(cur, "sales")
                journal_id = create_auto_journal(cur, date_value, f"فاتورة بيع {doc_no} - {product[0]}", debit_code, "4100", total) if group_posted else None
                tax_journal_id = None
                withholding_journal_id = None
                if group_posted and tax_amount > 0:
                    tax_journal_id = create_auto_journal(cur, date_value, f"ضريبة قيمة مضافة على فاتورة بيع {doc_no} - {product[0]}", debit_code, "2200", tax_amount)
                if group_posted and withholding_amount > 0:
                    withholding_journal_id = create_auto_journal(cur, date_value, f"ضريبة خصم وإضافة عميل على فاتورة بيع {doc_no}", "1510", debit_code, withholding_amount)
                cogs_journal_id = None
                if group_posted and cost_total > 0:
                    cogs_journal_id = create_auto_journal(cur, date_value, f"تكلفة بضاعة مباعة {doc_no} - {product[0]}", "6100", "1400", cost_total)
                cur.execute(
                    """
                    INSERT INTO sales_invoices(
                        date,due_date,doc_no,customer_id,product_id,quantity,unit_price,total,cost_total,
                        tax_rate,tax_amount,withholding_rate,withholding_amount,grand_total,payment_type,journal_id,tax_journal_id,withholding_journal_id,cogs_journal_id,status,
                        po_ref,gr_ref,notes
                    )
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        date_value,
                        due_date,
                        doc_no,
                        customer_id,
                        product_id,
                        quantity,
                        unit_price,
                        total,
                        cost_total,
                        tax_rate,
                        tax_amount,
                        withholding_rate,
                        withholding_amount,
                        grand_total,
                        payment_type,
                        journal_id,
                        tax_journal_id,
                        withholding_journal_id,
                        cogs_journal_id,
                        "posted" if group_posted else "draft",
                        po_ref,
                        gr_ref,
                        notes,
                    ),
                )
                invoice_id = cur.lastrowid
                mark_journal_source(cur, "sales", invoice_id, journal_id, tax_journal_id, withholding_journal_id, cogs_journal_id)
                if group_posted:
                    cur.execute("UPDATE products SET stock_quantity=stock_quantity-? WHERE id=?", (quantity, product_id))
                    cur.execute(
                        """
                        INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes)
                        VALUES (?,?,?,?,?,?,?)
                        """,
                        (date_value, product_id, "out", -quantity, "sale", invoice_id, "فاتورة بيع"),
                    )
                log_action(cur, "create", "sales_invoice", invoice_id, f"{doc_no}; total={grand_total}; withholding={withholding_amount}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash("تم حفظ فاتورة البيع." + (" تم ترحيلها وتحديث المخزون." if group_posted else " محفوظة كمسودة غير مرحلة."), "success")
                return redirect(url_for("sales"))

        cur.execute("SELECT id,name FROM customers ORDER BY name")
        customers_rows = cur.fetchall()
        cur.execute("SELECT id,name,sale_price,stock_quantity FROM products ORDER BY name")
        product_rows = cur.fetchall()
        cur.execute(
            """
            SELECT s.id,s.date,COALESCE(c.name,'بيع نقدي'),p.name,s.quantity,s.unit_price,
                   s.total,s.tax_amount,s.withholding_amount,s.grand_total,s.payment_type,s.status,s.cancel_reason,s.due_date,s.doc_no,
                   s.po_ref,s.gr_ref,s.notes
            FROM sales_invoices s
            LEFT JOIN customers c ON s.customer_id=c.id
            JOIN products p ON s.product_id=p.id
            ORDER BY s.id DESC
            """
        )
        invoices = cur.fetchall()
        conn.close()

        return render_template("sales.html", customers=customers_rows, products=product_rows, invoices=invoices)

    return sales


def build_purchases_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]
    next_document_number = deps["next_document_number"]
    default_tax_rate = deps["DEFAULT_TAX_RATE"]
    is_group_posted = deps["is_group_posted"]

    def purchases():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            supplier_invoice_no = request.form.get("supplier_invoice_no", "").strip()
            supplier_invoice_date = request.form.get("supplier_invoice_date", "").strip()
            due_date = request.form.get("due_date", "").strip()
            notes = request.form.get("notes", "").strip()
            supplier_id = request.form.get("supplier_id") or None
            product_id = request.form.get("product_id")
            payment_type = request.form.get("payment_type", "cash")
            tax_rate = parse_positive_amount(request.form.get("tax_rate", default_tax_rate))

            try:
                quantity = float(request.form.get("quantity", 0) or 0)
                unit_price = float(request.form.get("unit_price", 0) or 0)
            except ValueError:
                quantity = 0
                unit_price = 0
                flash("الكمية والسعر يجب أن يكونا أرقاما.", "danger")

            cur.execute("SELECT name FROM products WHERE id=?", (product_id,))
            product = cur.fetchone()
            _, withholding_rate = _supplier_withholding(cur, supplier_id)

            if not date_value:
                flash("تاريخ التسجيل مطلوب.", "danger")
            elif not supplier_invoice_no:
                flash("رقم فاتورة المورد مطلوب.", "danger")
            elif not supplier_invoice_date:
                flash("تاريخ فاتورة المورد مطلوب.", "danger")
            elif not product:
                flash("المنتج غير موجود.", "danger")
            elif payment_type == "credit" and not supplier_id:
                flash("اختر المورد عند الشراء الآجل.", "danger")
            elif quantity <= 0 or unit_price <= 0:
                flash("الكمية والسعر يجب أن يكونا أكبر من صفر.", "danger")
            elif tax_rate < 0:
                flash("نسبة الضريبة لا يمكن أن تكون سالبة.", "danger")
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
                withholding_amount = round(grand_total * withholding_rate / 100, 2)
                credit_code = "2100" if payment_type == "credit" else "1100"
                group_posted = is_group_posted(cur, "purchases")
                doc_no = next_document_number(cur, "purchases")
                journal_id = create_auto_journal(cur, date_value, f"فاتورة مورد {doc_no} - {product[0]}", "1400", credit_code, total) if group_posted else None
                tax_journal_id = None
                withholding_journal_id = None
                if group_posted and tax_amount > 0:
                    tax_journal_id = create_auto_journal(
                        cur,
                        date_value,
                        f"ضريبة قيمة مضافة على فاتورة مورد {doc_no} - {product[0]}",
                        "1500",
                        credit_code,
                        tax_amount,
                    )
                if group_posted and withholding_amount > 0:
                    withholding_debit = "2100" if payment_type == "credit" else "1100"
                    withholding_journal_id = create_auto_journal(cur, date_value, f"ضريبة خصم وإضافة مورد على فاتورة مورد {doc_no}", withholding_debit, "2230", withholding_amount)
                cur.execute(
                    """
                    INSERT INTO purchase_invoices(
                        date,doc_no,supplier_invoice_no,supplier_invoice_date,due_date,supplier_id,product_id,
                        quantity,unit_price,total,tax_rate,tax_amount,withholding_rate,withholding_amount,grand_total,payment_type,journal_id,tax_journal_id,withholding_journal_id,notes,status
                    )
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        date_value,
                        doc_no,
                        supplier_invoice_no,
                        supplier_invoice_date,
                        due_date,
                        supplier_id,
                        product_id,
                        quantity,
                        unit_price,
                        total,
                        tax_rate,
                        tax_amount,
                        withholding_rate,
                        withholding_amount,
                        grand_total,
                        payment_type,
                        journal_id,
                        tax_journal_id,
                        withholding_journal_id,
                        notes,
                        "posted" if group_posted else "draft",
                    ),
                )
                invoice_id = cur.lastrowid
                mark_journal_source(cur, "purchases", invoice_id, journal_id, tax_journal_id, withholding_journal_id)
                if group_posted:
                    cur.execute("UPDATE products SET stock_quantity=stock_quantity+?, purchase_price=? WHERE id=?", (quantity, unit_price, product_id))
                    cur.execute(
                        """
                        INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes)
                        VALUES (?,?,?,?,?,?,?)
                        """,
                        (date_value, product_id, "in", quantity, "purchase", invoice_id, "فاتورة شراء"),
                    )
                log_action(cur, "create", "purchase_invoice", invoice_id, f"{doc_no}; total={grand_total}; withholding={withholding_amount}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash("تم حفظ فاتورة المورد." + (" تم ترحيلها وتحديث المخزون." if group_posted else " محفوظة كمسودة غير مرحلة."), "success")
                return redirect(url_for("purchases"))

        cur.execute("SELECT id,name FROM suppliers ORDER BY name")
        suppliers_rows = cur.fetchall()
        cur.execute("SELECT id,name,purchase_price,stock_quantity FROM products ORDER BY name")
        product_rows = cur.fetchall()
        cur.execute(
            """
            SELECT p.id,p.date,COALESCE(s.name,'شراء نقدي'),pr.name,p.quantity,p.unit_price,
                   p.total,p.tax_amount,p.withholding_amount,p.grand_total,p.payment_type,p.status,p.cancel_reason,
                   p.supplier_invoice_no,p.supplier_invoice_date,p.due_date,p.doc_no
            FROM purchase_invoices p
            LEFT JOIN suppliers s ON p.supplier_id=s.id
            JOIN products pr ON p.product_id=pr.id
            ORDER BY p.id DESC
            """
        )
        invoices = cur.fetchall()
        conn.close()
        return render_template("purchases.html", suppliers=suppliers_rows, products=product_rows, invoices=invoices)

    return purchases


def _legacy_build_receipts_view(deps):
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
                    """
                    INSERT INTO receipt_vouchers(date,customer_id,amount,notes,journal_id,status)
                    VALUES (?,?,?,?,?,?)
                    """,
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


def _legacy_build_payments_view(deps):
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
                    """
                    INSERT INTO payment_vouchers(date,supplier_id,amount,notes,journal_id,status)
                    VALUES (?,?,?,?,?,?)
                    """,
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


def _legacy_build_print_receipt_view(deps):
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
        return render_template(
            "print_voucher.html",
            company=company,
            doc=doc,
            doc_type="سند قبض",
            party_label="العميل",
            amount_in_words=amount_to_words(doc[5]),
        )

    return print_receipt


def _legacy_build_print_payment_view(deps):
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
        return render_template(
            "print_voucher.html",
            company=company,
            doc=doc,
            doc_type="سند صرف",
            party_label="المورد",
            amount_in_words=amount_to_words(doc[5]),
        )

    return print_payment


def _legacy_build_customer_adjustments_view(deps):
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
                    (
                        date_value,
                        doc_no,
                        customer_id,
                        adjustment_type,
                        related_invoice_id,
                        description,
                        total,
                        tax_rate,
                        tax_amount,
                        grand_total,
                        journal_id,
                        tax_journal_id,
                        "posted" if group_posted else "draft",
                        notes,
                    ),
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
        cur.execute(
            """
            SELECT id,doc_no,date,grand_total
            FROM sales_invoices
            WHERE status='posted'
            ORDER BY id DESC
            """
        )
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


def _legacy_build_print_customer_adjustment_view(deps):
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
            amount_in_words=amount_to_words(doc[10]),
            source_label=f"مرجع الفاتورة: {doc[13]}" if doc[13] else "",
        )

    return print_customer_adjustment


def _legacy_build_prepare_customer_adjustment_einvoice_view(deps):
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
        flash("تم تجهيز التسوية للرفع على بورتال الضرائب." if created else "هذه التسوية مجهزة بالفعل للرفع.", "success")
        return redirect(url_for("customer_adjustments"))

    return prepare_customer_adjustment_einvoice


def _legacy_build_sales_orders_view(deps):
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
                flash("أضف صنفا واحدا على الأقل بكمية وسعر صحيحين.", "danger")
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


def _legacy_build_purchase_orders_view(deps):
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
                flash("أضف صنفا واحدا على الأقل بكمية وسعر صحيحين.", "danger")
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


def _legacy_build_print_purchase_order_view(deps):
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


def _legacy_build_sales_deliveries_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    parse_iso_date = deps["parse_iso_date"]
    ensure_open_period = deps["ensure_open_period"]
    next_document_number = deps["next_document_number"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]

    def sales_deliveries():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            line_id = int(parse_positive_amount(request.form.get("sales_order_line_id")) or 0)
            delivered_quantity = parse_positive_amount(request.form.get("delivered_quantity"))
            notes = request.form.get("notes", "").strip()
            cur.execute(
                """
                SELECT so.id,sol.id,so.customer_id,sol.product_id,sol.quantity,sol.unit_price,sol.tax_rate,p.name,p.purchase_price,p.stock_quantity,so.date,so.delivery_date
                FROM sales_order_lines sol
                JOIN sales_orders so ON so.id=sol.order_id
                JOIN products p ON p.id=sol.product_id
                WHERE sol.id=?
                """,
                (line_id,),
            )
            order = cur.fetchone()
            cur.execute("SELECT COALESCE(SUM(delivered_quantity),0) FROM sales_delivery_notes WHERE sales_order_line_id=?", (line_id,))
            already_delivered = cur.fetchone()[0] if order else 0
            remaining = (order[4] - already_delivered) if order else 0
            movement_date = parse_iso_date(date_value)
            order_date = parse_iso_date(order[10]) if order else None
            planned_delivery_date = parse_iso_date(order[11]) if order else None
            if not date_value:
                flash("تاريخ إذن الصرف مطلوب.", "danger")
            elif not order:
                flash("بند أمر البيع غير موجود.", "danger")
            elif movement_date and order_date and movement_date < order_date:
                flash("تاريخ إذن الصرف لا يمكن أن يكون أسبق من تاريخ أمر البيع.", "danger")
            elif movement_date and planned_delivery_date and movement_date < planned_delivery_date:
                flash("تاريخ إذن الصرف لا يمكن أن يكون أسبق من تاريخ التوريد المحدد في أمر البيع.", "danger")
            elif delivered_quantity <= 0 or delivered_quantity > remaining:
                flash("الكمية المنصرفة يجب أن تكون أكبر من صفر ولا تتجاوز المتبقي.", "danger")
            elif delivered_quantity > order[9]:
                flash("رصيد المخزون لا يكفي لإذن الصرف.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("sales_deliveries"))
                delivery_no = next_document_number(cur, "sales_delivery_notes")
                total = delivered_quantity * order[5]
                cost_total = delivered_quantity * order[8]
                tax_amount = total * order[6] / 100
                grand_total = total + tax_amount
                cogs_journal_id = create_auto_journal(cur, date_value, f"إذن صرف مبيعات {delivery_no} - {order[7]}", "6100", "1400", cost_total) if cost_total > 0 else None
                cur.execute(
                    """
                    INSERT INTO sales_delivery_notes(delivery_no,date,sales_order_id,sales_order_line_id,customer_id,product_id,ordered_quantity,delivered_quantity,unit_price,total,cost_total,tax_rate,tax_amount,grand_total,cogs_journal_id,notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (delivery_no, date_value, order[0], order[1], order[2], order[3], order[4], delivered_quantity, order[5], total, cost_total, order[6], tax_amount, grand_total, cogs_journal_id, notes),
                )
                delivery_id = cur.lastrowid
                mark_journal_source(cur, "sales_delivery", delivery_id, cogs_journal_id)
                cur.execute("UPDATE products SET stock_quantity=stock_quantity-? WHERE id=?", (delivered_quantity, order[3]))
                cur.execute(
                    "INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes) VALUES (?,?,?,?,?,?,?)",
                    (date_value, order[3], "out", -delivered_quantity, "sales_delivery", delivery_id, f"إذن صرف {delivery_no}"),
                )
                log_action(cur, "create", "sales_delivery", delivery_id, f"{delivery_no}; total={grand_total}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash(f"تم تسجيل إذن الصرف {delivery_no}.", "success")
                return redirect(url_for("sales_deliveries"))

        cur.execute(
            """
            SELECT sol.id,so.id,so.date,COALESCE(c.name,'بيع نقدي'),p.name,sol.quantity,sol.unit_price,
                   sol.quantity-COALESCE(SUM(sd.delivered_quantity),0) AS remaining
            FROM sales_order_lines sol
            JOIN sales_orders so ON so.id=sol.order_id
            LEFT JOIN customers c ON c.id=so.customer_id
            JOIN products p ON p.id=sol.product_id
            LEFT JOIN sales_delivery_notes sd ON sd.sales_order_line_id=sol.id
            GROUP BY sol.id
            HAVING remaining > 0
            ORDER BY so.id DESC, sol.id
            """
        )
        open_orders = cur.fetchall()
        cur.execute(
            """
            SELECT sd.id,sd.delivery_no,sd.date,sd.sales_order_id,COALESCE(c.name,'بيع نقدي'),p.name,
                   sd.delivered_quantity,sd.unit_price,sd.grand_total,sd.invoice_id
            FROM sales_delivery_notes sd
            LEFT JOIN customers c ON c.id=sd.customer_id
            JOIN products p ON p.id=sd.product_id
            ORDER BY sd.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("sales_deliveries.html", open_orders=open_orders, rows=rows)

    return sales_deliveries


def _legacy_build_purchase_receipts_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    parse_iso_date = deps["parse_iso_date"]
    ensure_open_period = deps["ensure_open_period"]
    next_document_number = deps["next_document_number"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]

    def purchase_receipts():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            line_id = int(parse_positive_amount(request.form.get("purchase_order_line_id")) or 0)
            received_quantity = parse_positive_amount(request.form.get("received_quantity"))
            notes = request.form.get("notes", "").strip()
            cur.execute(
                """
                SELECT po.id,pol.id,po.supplier_id,pol.product_id,pol.quantity,pol.unit_price,pol.tax_rate,p.name,po.date,po.delivery_date
                FROM purchase_order_lines pol
                JOIN purchase_orders po ON po.id=pol.order_id
                JOIN products p ON p.id=pol.product_id
                WHERE pol.id=?
                """,
                (line_id,),
            )
            order = cur.fetchone()
            cur.execute("SELECT COALESCE(SUM(received_quantity),0) FROM purchase_receipts WHERE purchase_order_line_id=?", (line_id,))
            already_received = cur.fetchone()[0] if order else 0
            remaining = (order[4] - already_received) if order else 0
            movement_date = parse_iso_date(date_value)
            order_date = parse_iso_date(order[8]) if order else None
            planned_supply_date = parse_iso_date(order[9]) if order else None
            if not date_value:
                flash("تاريخ إذن الاستلام مطلوب.", "danger")
            elif not order:
                flash("بند أمر الشراء غير موجود.", "danger")
            elif movement_date and order_date and movement_date < order_date:
                flash("تاريخ إذن الاستلام لا يمكن أن يكون أسبق من تاريخ أمر الشراء.", "danger")
            elif movement_date and planned_supply_date and movement_date < planned_supply_date:
                flash("تاريخ إذن الاستلام لا يمكن أن يكون أسبق من تاريخ التوريد المحدد في أمر الشراء.", "danger")
            elif received_quantity <= 0 or received_quantity > remaining:
                flash("الكمية المستلمة يجب أن تكون أكبر من صفر ولا تتجاوز المتبقي.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("purchase_receipts"))
                receipt_no = next_document_number(cur, "purchase_receipts")
                total = received_quantity * order[5]
                tax_amount = total * order[6] / 100
                grand_total = total + tax_amount
                journal_id = create_auto_journal(cur, date_value, f"إذن استلام مخزني {receipt_no} - {order[7]}", "1400", "2150", total)
                cur.execute(
                    """
                    INSERT INTO purchase_receipts(receipt_no,date,purchase_order_id,purchase_order_line_id,supplier_id,product_id,ordered_quantity,received_quantity,unit_price,total,tax_rate,tax_amount,grand_total,journal_id,notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (receipt_no, date_value, order[0], order[1], order[2], order[3], order[4], received_quantity, order[5], total, order[6], tax_amount, grand_total, journal_id, notes),
                )
                receipt_id = cur.lastrowid
                mark_journal_source(cur, "purchase_receipt", receipt_id, journal_id)
                cur.execute("UPDATE products SET stock_quantity=stock_quantity+?, purchase_price=? WHERE id=?", (received_quantity, order[5], order[3]))
                cur.execute(
                    "INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes) VALUES (?,?,?,?,?,?,?)",
                    (date_value, order[3], "in", received_quantity, "purchase_receipt", receipt_id, f"إذن استلام {receipt_no}"),
                )
                log_action(cur, "create", "purchase_receipt", receipt_id, f"{receipt_no}; total={grand_total}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash(f"تم تسجيل إذن الاستلام {receipt_no}.", "success")
                return redirect(url_for("purchase_receipts"))

        cur.execute(
            """
            SELECT pol.id,po.id,po.date,s.name,p.name,pol.quantity,pol.unit_price,
                   pol.quantity-COALESCE(SUM(pr.received_quantity),0) AS remaining
            FROM purchase_order_lines pol
            JOIN purchase_orders po ON po.id=pol.order_id
            JOIN suppliers s ON s.id=po.supplier_id
            JOIN products p ON p.id=pol.product_id
            LEFT JOIN purchase_receipts pr ON pr.purchase_order_line_id=pol.id
            GROUP BY pol.id
            HAVING remaining > 0
            ORDER BY po.id DESC, pol.id
            """
        )
        open_orders = cur.fetchall()
        cur.execute(
            """
            SELECT pr.id,pr.receipt_no,pr.date,pr.purchase_order_id,s.name,p.name,
                   pr.received_quantity,pr.unit_price,pr.grand_total,pr.invoice_id
            FROM purchase_receipts pr
            JOIN suppliers s ON s.id=pr.supplier_id
            JOIN products p ON p.id=pr.product_id
            ORDER BY pr.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("purchase_receipts.html", open_orders=open_orders, rows=rows)

    return purchase_receipts


def _legacy_build_sales_returns_view(deps):
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
                    journal_id = create_auto_journal(cur, date_value, f"مردود بيع - {product[0]}", "4200", credit_code, total)
                    tax_journal_id = create_auto_journal(cur, date_value, f"ضريبة مردود بيع - {product[0]}", "2200", credit_code, tax_amount) if tax_amount > 0 else None
                    cogs_journal_id = create_auto_journal(cur, date_value, f"عكس تكلفة مردود بيع - {product[0]}", "1400", "6100", cost_total) if cost_total > 0 else None
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


def _legacy_build_purchase_returns_view(deps):
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


def _legacy_build_sales_credit_notes_view(deps):
    db = deps["db"]
    ensure_open_period = deps["ensure_open_period"]
    next_document_number = deps["next_document_number"]
    log_action = deps["log_action"]

    def sales_credit_notes():
        conn = db()
        cur = conn.cursor()

        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            sales_return_id = int(deps["parse_positive_amount"](request.form.get("sales_return_id")) or 0)
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
                flash("تاريخ الكريدت نوت مطلوب.", "danger")
            elif not sales_return:
                flash("مردود المبيعات المحدد غير موجود.", "danger")
            elif existing:
                flash("تم إصدار كريدت نوت لهذا المردود من قبل.", "danger")
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
                flash(f"تم إنشاء الكريدت نوت {doc_no}.", "success")
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


def _legacy_build_print_purchase_view(deps):
    db = deps["db"]
    get_company_settings = deps["get_company_settings"]
    amount_to_words = deps["amount_to_words"]

    def print_purchase(id):
        conn = db()
        cur = conn.cursor()
        company = get_company_settings(cur)
        cur.execute(
            """
            SELECT p.id,p.date,COALESCE(s.name,'شراء نقدي'),COALESCE(s.phone,''),COALESCE(s.address,''),
                   pr.name,pr.unit,p.quantity,p.unit_price,p.total,p.tax_rate,p.tax_amount,p.grand_total,
                   p.payment_type,p.status,p.cancel_reason,p.supplier_invoice_no,p.supplier_invoice_date,p.due_date
            FROM purchase_invoices p
            LEFT JOIN suppliers s ON p.supplier_id=s.id
            JOIN products pr ON p.product_id=pr.id
            WHERE p.id=?
            """,
            (id,),
        )
        doc = cur.fetchone()
        conn.close()
        if not doc:
            flash("فاتورة الشراء غير موجودة.", "danger")
            return redirect(url_for("purchases"))
        return render_template(
            "print_document.html",
            company=company,
            doc=doc,
            doc_type="تسجيل فاتورة مورد",
            party_label="المورد",
            supplier_invoice=True,
            amount_in_words=amount_to_words(doc[12]),
        )

    return print_purchase


def _legacy_build_print_sales_credit_note_view(deps):
    db = deps["db"]
    get_company_settings = deps["get_company_settings"]
    amount_to_words = deps["amount_to_words"]

    def print_sales_credit_note(id):
        conn = db()
        cur = conn.cursor()
        company = get_company_settings(cur)
        cur.execute(
            """
            SELECT scn.id,scn.date,scn.doc_no,COALESCE(c.name,'عميل نقدي'),COALESCE(c.phone,''),COALESCE(c.address,''),
                   p.name,p.unit,scn.quantity,scn.unit_price,scn.total,scn.tax_amount,scn.grand_total,
                   scn.notes,scn.sales_return_id,scn.sales_invoice_id
            FROM sales_credit_notes scn
            LEFT JOIN customers c ON c.id=scn.customer_id
            LEFT JOIN products p ON p.id=scn.product_id
            WHERE scn.id=?
            """,
            (id,),
        )
        doc = cur.fetchone()
        conn.close()
        if not doc:
            flash("الكريدت نوت غير موجود.", "danger")
            return redirect(url_for("sales_credit_notes"))
        return render_template(
            "print_customer_note.html",
            company=company,
            doc=doc,
            doc_title="كريدت نوت عميل",
            note_kind="credit",
            amount_in_words=amount_to_words(doc[12]),
            source_label=f"من واقع مردود المبيعات #{doc[14]} / الفاتورة الأصلية #{doc[15]}",
        )

    return print_sales_credit_note


def _legacy_build_prepare_sales_credit_note_einvoice_view(deps):
    db = deps["db"]
    prepare_einvoice_document = deps["prepare_einvoice_document"]
    log_action = deps["log_action"]

    def prepare_sales_credit_note_einvoice(id):
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM sales_credit_notes WHERE id=?", (id,))
        if not cur.fetchone():
            conn.close()
            flash("الكريدت نوت غير موجود.", "danger")
            return redirect(url_for("sales_credit_notes"))
        _, created = prepare_einvoice_document(cur, "sales_credit_note", id)
        log_action(cur, "prepare", "e_invoice_documents", None, f"sales_credit_note={id}")
        conn.commit()
        conn.close()
        flash("تم تجهيز الكريدت نوت للرفع على بورتال الضرائب." if created else "الكريدت نوت مجهز بالفعل للرفع.", "success")
        return redirect(url_for("sales_credit_notes"))

    return prepare_sales_credit_note_einvoice
