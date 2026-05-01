from flask import flash, redirect, render_template, request, url_for
from modules.accounting.ledger_engine import post_simple_entry


def _add_column_if_missing(cur, table, column, definition):
    cur.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cur.fetchall()]
    if column not in columns:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _ensure_treasury_extensions(cur):
    """Safe runtime migration for manual treasury vouchers.

    Existing receipt_vouchers/payment_vouchers tables keep customer_id/supplier_id
    as NOT NULL, so manual vouchers use a hidden generic customer/supplier row
    while the selected account is stored in account_id.
    """
    _add_column_if_missing(cur, "receipt_vouchers", "voucher_type", "TEXT NOT NULL DEFAULT 'customer_receipt'")
    _add_column_if_missing(cur, "receipt_vouchers", "account_id", "INTEGER")
    _add_column_if_missing(cur, "payment_vouchers", "voucher_type", "TEXT NOT NULL DEFAULT 'supplier_payment'")
    _add_column_if_missing(cur, "payment_vouchers", "account_id", "INTEGER")


def _get_or_create_generic_customer(cur):
    name = "حساب عام - سند قبض"
    cur.execute("SELECT id FROM customers WHERE name=?", (name,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        """
        INSERT INTO customers(name, phone, address, withholding_status)
        VALUES (?, '', '', 'non_subject')
        """,
        (name,),
    )
    return cur.lastrowid


def _get_or_create_generic_supplier(cur):
    name = "حساب عام - سند صرف"
    cur.execute("SELECT id FROM suppliers WHERE name=?", (name,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        """
        INSERT INTO suppliers(name, phone, address, withholding_status)
        VALUES (?, '', '', 'exempt')
        """,
        (name,),
    )
    return cur.lastrowid


def _fetch_cash_accounts(cur):
    # خزنة وبنك كطرف نقدي. لو حبيت تضيف حسابات تانية عدّل الأكواد هنا.
    cur.execute(
        """
        SELECT id, code, name
        FROM accounts
        WHERE code IN ('1100','1110','1120','1200','1210')
        ORDER BY code
        """
    )
    rows = cur.fetchall()
    if rows:
        return rows
    cur.execute("SELECT id, code, name FROM accounts ORDER BY code")
    return cur.fetchall()


def _fetch_general_accounts(cur):
    cur.execute(
        """
        SELECT id, code, name
        FROM accounts
        WHERE code NOT IN ('1100','1110','1120','1200','1210')
        ORDER BY code
        """
    )
    return cur.fetchall()


def _normalize_text(value):
    return (value or "").strip().lower()


def _account_meta(cur, account_id):
    """
    يرجع بيانات الحساب كاملة لاستخدامها في فلترة سندات القبض والصرف.
    يعتمد أساسًا على نوع الحساب، ومعه طبقة حماية بالكلمات والكود.
    """
    cur.execute("SELECT id, code, name, type FROM accounts WHERE id=?", (account_id,))
    return cur.fetchone()


def _is_blocked_treasury_account(code, name, account_type, direction):
    """
    Enterprise guard:
    - direction='receipt': الحساب المختار هو الطرف الدائن في سند القبض.
    - direction='payment': الحساب المختار هو الطرف المدين في سند الصرف.

    الهدف: منع الحسابات الحساسة التي يجب أن تتحرك من دورة البيع/الشراء/المخزون فقط.
    """
    code = str(code or "").strip()
    name_l = _normalize_text(name)
    type_l = _normalize_text(account_type)

    # حسابات لا تدخل كسند قبض/صرف يدوي عام إطلاقًا
    globally_blocked_keywords = [
        "مخزون",
        "بضاعة",
        "تكلفة البضاعة",
        "رأس المال",
        "ارباح",
        "أرباح",
        "مجمع إهلاك",
        "ضريبة قيمة مضافة - مخرجات",
        "ضريبة قيمة مضافة - مدخلات",
    ]

    # حماية إضافية بالأكواد الرئيسية الحالية، بدون الاعتماد عليها وحدها
    globally_blocked_codes = {
        "1400",  # المخزون
        "4100",  # إيرادات المبيعات
        "6100",  # تكلفة البضاعة
    }

    if code in globally_blocked_codes:
        return True
    if any(keyword.lower() in name_l for keyword in globally_blocked_keywords):
        return True

    if direction == "receipt":
        # في القبض لا تختار مصروفات أو أصول مخزنية/ثابتة كرأس طرف دائن عام
        blocked_types = {"مصروفات", "أصول", "حقوق ملكية"}
        blocked_keywords = ["مصروف", "تكلفة", "أصل ثابت", "أصول ثابتة"]
        if type_l in {_normalize_text(t) for t in blocked_types}:
            return True
        if any(keyword.lower() in name_l for keyword in blocked_keywords):
            return True

    elif direction == "payment":
        # في الصرف لا تختار إيرادات/مبيعات/عملاء كرأس طرف مدين عام
        blocked_types = {"إيرادات", "حقوق ملكية"}
        blocked_keywords = ["مبيعات", "إيراد", "إيرادات", "عميل", "عملاء"]
        if type_l in {_normalize_text(t) for t in blocked_types}:
            return True
        if any(keyword.lower() in name_l for keyword in blocked_keywords):
            return True

    return False


def _fetch_allowed_treasury_accounts(cur, direction):
    """
    ترجع الحسابات المسموحة للعرض في سند القبض أو الصرف.
    شكل الخرج يظل (id, code, name) حتى لا نكسر القوالب الحالية.
    """
    cur.execute(
        """
        SELECT id, code, name, type
        FROM accounts
        WHERE code NOT IN ('1100','1110','1120','1200','1210')
        ORDER BY code
        """
    )
    allowed = []
    for account_id, code, name, account_type in cur.fetchall():
        if not _is_blocked_treasury_account(code, name, account_type, direction):
            allowed.append((account_id, code, name))
    return allowed


def _validate_manual_treasury_account(cur, account_id, direction):
    """
    حماية Backend: حتى لو المستخدم عدل HTML يدويًا، نمنع الحساب غير المسموح.
    """
    if not account_id:
        return False, "الحساب العام غير موجود."

    row = _account_meta(cur, account_id)
    if not row:
        return False, "الحساب العام غير موجود."

    _, code, name, account_type = row
    if _is_blocked_treasury_account(code, name, account_type, direction):
        if direction == "receipt":
            return False, "هذا الحساب غير مسموح استخدامه كسند قبض يدوي. استخدم شاشة العملية الأصلية أو اختر حسابًا مناسبًا."
        return False, "هذا الحساب غير مسموح استخدامه كسند صرف يدوي. استخدم شاشة العملية الأصلية أو اختر حسابًا مناسبًا."

    return True, ""



def _account_code_name(cur, account_id):
    cur.execute("SELECT code, name FROM accounts WHERE id=?", (account_id,))
    return cur.fetchone()


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
        _ensure_treasury_extensions(cur)

        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            account_type = request.form.get("account_type", "customer").strip()
            customer_id = request.form.get("customer_id")
            cash_account_id = request.form.get("cash_account_id")
            account_id = request.form.get("account_id")
            amount = parse_positive_amount(request.form.get("amount"))
            notes = request.form.get("notes", "").strip()

            customer = None
            selected_account = None
            cash_account = _account_code_name(cur, cash_account_id) if cash_account_id else None

            if account_type == "customer" and customer_id:
                cur.execute("SELECT name FROM customers WHERE id=?", (customer_id,))
                customer = cur.fetchone()
            elif account_type == "account" and account_id:
                selected_account = _account_code_name(cur, account_id)

            if not date_value:
                flash("التاريخ مطلوب.", "danger")
            elif not cash_account:
                flash("اختر حساب الخزينة أو البنك.", "danger")
            elif account_type == "customer" and not customer:
                flash("العميل غير موجود.", "danger")
            elif account_type == "account" and not selected_account:
                flash("الحساب العام غير موجود.", "danger")
            elif account_type == "account" and not _validate_manual_treasury_account(cur, account_id, "receipt")[0]:
                flash(_validate_manual_treasury_account(cur, account_id, "receipt")[1], "danger")
            elif account_type not in ("customer", "account"):
                flash("نوع الحساب غير صحيح.", "danger")
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
                journal_id = None

                if account_type == "customer":
                    voucher_type = "customer_receipt"
                    party_id = customer_id
                    stored_account_id = None
                    description = f"سند قبض من {customer[0]}"
                    debit_code = cash_account[0]
                    credit_code = "1300"
                else:
                    voucher_type = "manual_receipt"
                    party_id = _get_or_create_generic_customer(cur)
                    stored_account_id = int(account_id)
                    description = f"سند قبض من حساب {selected_account[1]}"
                    debit_code = cash_account[0]
                    credit_code = selected_account[0]

                if group_posted:
                    journal_id = post_simple_entry(
                        cur=cur,
                        date=date_value,
                        description=description,
                        debit_code=debit_code,
                        credit_code=credit_code,
                        amount=amount,
                        source_type="receipts",
                    )

                cur.execute(
                    """
                    INSERT INTO receipt_vouchers(
                        date, customer_id, amount, notes, journal_id, status, voucher_type, account_id
                    )
                    VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (
                        date_value,
                        party_id,
                        amount,
                        notes,
                        journal_id,
                        "posted" if group_posted else "draft",
                        voucher_type,
                        stored_account_id,
                    ),
                )
                voucher_id = cur.lastrowid
                mark_journal_source(cur, "receipts", voucher_id, journal_id)
                log_action(cur, "create", "receipt_voucher", voucher_id, f"type={voucher_type}; amount={amount}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash("تم حفظ سند القبض." + (" تم ترحيله." if group_posted else " محفوظ كمسودة غير مرحلة."), "success")
                return redirect(url_for("receipts"))

        cur.execute("SELECT id,name FROM customers WHERE name!='حساب عام - سند قبض' ORDER BY name")
        customers_rows = cur.fetchall()
        cash_accounts = _fetch_cash_accounts(cur)
        general_accounts = _fetch_allowed_treasury_accounts(cur, "receipt")

        cur.execute(
            """
            SELECT
                r.id,
                r.date,
                CASE
                    WHEN COALESCE(r.voucher_type,'customer_receipt')='manual_receipt'
                    THEN COALESCE(a.code || ' - ' || a.name, 'حساب عام')
                    ELSE COALESCE(c.name, 'عميل')
                END AS party_name,
                r.amount,
                r.notes,
                r.status,
                r.cancel_reason,
                COALESCE(r.voucher_type,'customer_receipt') AS voucher_type
            FROM receipt_vouchers r
            LEFT JOIN customers c ON r.customer_id=c.id
            LEFT JOIN accounts a ON r.account_id=a.id
            ORDER BY r.id DESC
            """
        )
        rows = cur.fetchall()
        conn.commit()
        conn.close()
        return render_template(
            "receipts.html",
            customers=customers_rows,
            cash_accounts=cash_accounts,
            accounts=general_accounts,
            rows=rows,
        )

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
        _ensure_treasury_extensions(cur)

        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            account_type = request.form.get("account_type", "supplier").strip()
            supplier_id = request.form.get("supplier_id")
            cash_account_id = request.form.get("cash_account_id")
            account_id = request.form.get("account_id")
            amount = parse_positive_amount(request.form.get("amount"))
            notes = request.form.get("notes", "").strip()

            supplier = None
            selected_account = None
            cash_account = _account_code_name(cur, cash_account_id) if cash_account_id else None

            if account_type == "supplier" and supplier_id:
                cur.execute("SELECT name FROM suppliers WHERE id=?", (supplier_id,))
                supplier = cur.fetchone()
            elif account_type == "account" and account_id:
                selected_account = _account_code_name(cur, account_id)

            if not date_value:
                flash("التاريخ مطلوب.", "danger")
            elif not cash_account:
                flash("اختر حساب الخزينة أو البنك.", "danger")
            elif account_type == "supplier" and not supplier:
                flash("المورد غير موجود.", "danger")
            elif account_type == "account" and not selected_account:
                flash("الحساب العام غير موجود.", "danger")
            elif account_type == "account" and not _validate_manual_treasury_account(cur, account_id, "payment")[0]:
                flash(_validate_manual_treasury_account(cur, account_id, "payment")[1], "danger")
            elif account_type not in ("supplier", "account"):
                flash("نوع الحساب غير صحيح.", "danger")
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
                journal_id = None

                if account_type == "supplier":
                    voucher_type = "supplier_payment"
                    party_id = supplier_id
                    stored_account_id = None
                    description = f"سند صرف إلى {supplier[0]}"
                    debit_code = "2100"
                    credit_code = cash_account[0]
                else:
                    voucher_type = "manual_payment"
                    party_id = _get_or_create_generic_supplier(cur)
                    stored_account_id = int(account_id)
                    description = f"سند صرف إلى حساب {selected_account[1]}"
                    debit_code = selected_account[0]
                    credit_code = cash_account[0]

                if group_posted:
                    journal_id = post_simple_entry(
                        cur=cur,
                        date=date_value,
                        description=description,
                        debit_code=debit_code,
                        credit_code=credit_code,
                        amount=amount,
                        source_type="payments",
                    )

                cur.execute(
                    """
                    INSERT INTO payment_vouchers(
                        date, supplier_id, amount, notes, journal_id, status, voucher_type, account_id
                    )
                    VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (
                        date_value,
                        party_id,
                        amount,
                        notes,
                        journal_id,
                        "posted" if group_posted else "draft",
                        voucher_type,
                        stored_account_id,
                    ),
                )
                voucher_id = cur.lastrowid
                mark_journal_source(cur, "payments", voucher_id, journal_id)
                log_action(cur, "create", "payment_voucher", voucher_id, f"type={voucher_type}; amount={amount}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash("تم حفظ سند الصرف." + (" تم ترحيله." if group_posted else " محفوظ كمسودة غير مرحلة."), "success")
                return redirect(url_for("payments"))

        cur.execute("SELECT id,name FROM suppliers WHERE name!='حساب عام - سند صرف' ORDER BY name")
        suppliers_rows = cur.fetchall()
        cash_accounts = _fetch_cash_accounts(cur)
        general_accounts = _fetch_allowed_treasury_accounts(cur, "payment")

        cur.execute(
            """
            SELECT
                p.id,
                p.date,
                CASE
                    WHEN COALESCE(p.voucher_type,'supplier_payment')='manual_payment'
                    THEN COALESCE(a.code || ' - ' || a.name, 'حساب عام')
                    ELSE COALESCE(s.name, 'مورد')
                END AS party_name,
                p.amount,
                p.notes,
                p.status,
                p.cancel_reason,
                COALESCE(p.voucher_type,'supplier_payment') AS voucher_type
            FROM payment_vouchers p
            LEFT JOIN suppliers s ON p.supplier_id=s.id
            LEFT JOIN accounts a ON p.account_id=a.id
            ORDER BY p.id DESC
            """
        )
        rows = cur.fetchall()
        conn.commit()
        conn.close()
        return render_template(
            "payments.html",
            suppliers=suppliers_rows,
            cash_accounts=cash_accounts,
            accounts=general_accounts,
            rows=rows,
        )

    return payments


def build_print_receipt_view(deps):
    db = deps["db"]
    get_company_settings = deps["get_company_settings"]
    amount_to_words = deps["amount_to_words"]

    def print_receipt(id):
        conn = db()
        cur = conn.cursor()
        _ensure_treasury_extensions(cur)
        company = get_company_settings(cur)
        cur.execute(
            """
            SELECT
                r.id,
                r.date,
                CASE
                    WHEN COALESCE(r.voucher_type,'customer_receipt')='manual_receipt'
                    THEN COALESCE(a.code || ' - ' || a.name, 'حساب عام')
                    ELSE COALESCE(c.name, 'عميل')
                END AS party_name,
                CASE
                    WHEN COALESCE(r.voucher_type,'customer_receipt')='manual_receipt' THEN ''
                    ELSE COALESCE(c.phone,'')
                END AS phone,
                CASE
                    WHEN COALESCE(r.voucher_type,'customer_receipt')='manual_receipt' THEN ''
                    ELSE COALESCE(c.address,'')
                END AS address,
                r.amount,
                r.notes,
                r.status,
                r.cancel_reason
            FROM receipt_vouchers r
            LEFT JOIN customers c ON r.customer_id=c.id
            LEFT JOIN accounts a ON r.account_id=a.id
            WHERE r.id=?
            """,
            (id,),
        )
        doc = cur.fetchone()
        conn.commit()
        conn.close()
        if not doc:
            flash("سند القبض غير موجود.", "danger")
            return redirect(url_for("receipts"))
        return render_template("print_voucher.html", company=company, doc=doc, doc_type="سند قبض", party_label="الطرف", amount_in_words=amount_to_words(doc[5]))

    return print_receipt


def build_print_payment_view(deps):
    db = deps["db"]
    get_company_settings = deps["get_company_settings"]
    amount_to_words = deps["amount_to_words"]

    def print_payment(id):
        conn = db()
        cur = conn.cursor()
        _ensure_treasury_extensions(cur)
        company = get_company_settings(cur)
        cur.execute(
            """
            SELECT
                p.id,
                p.date,
                CASE
                    WHEN COALESCE(p.voucher_type,'supplier_payment')='manual_payment'
                    THEN COALESCE(a.code || ' - ' || a.name, 'حساب عام')
                    ELSE COALESCE(s.name, 'مورد')
                END AS party_name,
                CASE
                    WHEN COALESCE(p.voucher_type,'supplier_payment')='manual_payment' THEN ''
                    ELSE COALESCE(s.phone,'')
                END AS phone,
                CASE
                    WHEN COALESCE(p.voucher_type,'supplier_payment')='manual_payment' THEN ''
                    ELSE COALESCE(s.address,'')
                END AS address,
                p.amount,
                p.notes,
                p.status,
                p.cancel_reason
            FROM payment_vouchers p
            LEFT JOIN suppliers s ON p.supplier_id=s.id
            LEFT JOIN accounts a ON p.account_id=a.id
            WHERE p.id=?
            """,
            (id,),
        )
        doc = cur.fetchone()
        conn.commit()
        conn.close()
        if not doc:
            flash("سند الصرف غير موجود.", "danger")
            return redirect(url_for("payments"))
        return render_template("print_voucher.html", company=company, doc=doc, doc_type="سند صرف", party_label="الطرف", amount_in_words=amount_to_words(doc[5]))

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
