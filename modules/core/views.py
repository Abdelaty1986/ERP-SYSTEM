import os

from flask import flash, redirect, render_template, request, session, url_for


def build_dashboard_view(deps):
    db = deps["db"]
    build_aging_rows = deps["build_aging_rows"]

    def dashboard():
        conn = db()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM journal")
        entries = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM accounts")
        accounts_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM customers")
        customers_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM suppliers")
        suppliers_count = cur.fetchone()[0]

        cur.execute("SELECT COALESCE(SUM(amount),0) FROM journal")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM products")
        products_count = cur.fetchone()[0]

        cur.execute("SELECT COALESCE(SUM(stock_quantity * purchase_price),0) FROM products")
        inventory_value = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM products WHERE stock_quantity <= 5")
        low_stock_count = cur.fetchone()[0]

        cur.execute(
            """
            SELECT
                (SELECT COALESCE(SUM(grand_total),0) FROM sales_invoices WHERE status='posted') +
                (SELECT COALESCE(SUM(grand_total),0) FROM financial_sales_invoices WHERE status='posted')
            """
        )
        sales_total = cur.fetchone()[0]

        cur.execute("SELECT COALESCE(SUM(grand_total),0) FROM purchase_invoices WHERE status='posted'")
        purchases_total = cur.fetchone()[0]

        cur.execute(
            """
            SELECT
                (SELECT COALESCE(SUM(grand_total - COALESCE(withholding_amount,0)),0) FROM sales_invoices WHERE status='posted' AND payment_type='credit') +
                (SELECT COALESCE(SUM(grand_total - COALESCE(withholding_amount,0)),0) FROM financial_sales_invoices WHERE status='posted' AND payment_type='credit')
            """
        )
        customer_credit_total = cur.fetchone()[0]

        cur.execute("SELECT COALESCE(SUM(amount),0) FROM receipt_vouchers WHERE status='posted'")
        receipts_total = cur.fetchone()[0]
        customer_balance_total = customer_credit_total - receipts_total

        cur.execute(
            """
            SELECT COALESCE(SUM(grand_total - COALESCE(withholding_amount,0)),0)
            FROM purchase_invoices
            WHERE status='posted' AND payment_type='credit'
            """
        )
        supplier_credit_total = cur.fetchone()[0]

        cur.execute("SELECT COALESCE(SUM(amount),0) FROM payment_vouchers WHERE status='posted'")
        payments_total = cur.fetchone()[0]
        supplier_balance_total = supplier_credit_total - payments_total
        net_cash_movement = receipts_total - payments_total

        cur.execute("SELECT COUNT(*) FROM sales_orders")
        sales_orders_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM purchase_orders")
        purchase_orders_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM sales_delivery_notes")
        delivery_notes_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM purchase_receipts")
        receipt_notes_count = cur.fetchone()[0]

        cur.execute(
            """
            SELECT c.id,c.name,s.date,s.due_date,(s.grand_total - COALESCE(s.withholding_amount,0))
            FROM sales_invoices s
            JOIN customers c ON c.id=s.customer_id
            WHERE s.status='posted' AND s.payment_type='credit'
            """
        )
        customer_aging_invoices = cur.fetchall()
        cur.execute(
            """
            SELECT customer_id,COALESCE(SUM(amount),0)
            FROM receipt_vouchers
            WHERE status='posted'
            GROUP BY customer_id
            """
        )
        customer_settlements = cur.fetchall()
        customer_aging_rows, _ = build_aging_rows(customer_aging_invoices, customer_settlements)
        overdue_customer_invoices = sum(1 for row in customer_aging_rows if sum(row[3:7]) > 0)

        cur.execute(
            """
            SELECT s.id,s.name,p.date,p.due_date,(p.grand_total - COALESCE(p.withholding_amount,0))
            FROM purchase_invoices p
            JOIN suppliers s ON s.id=p.supplier_id
            WHERE p.status='posted' AND p.payment_type='credit'
            """
        )
        supplier_aging_invoices = cur.fetchall()
        cur.execute(
            """
            SELECT supplier_id,COALESCE(SUM(amount),0)
            FROM payment_vouchers
            WHERE status='posted'
            GROUP BY supplier_id
            """
        )
        supplier_settlements = cur.fetchall()
        supplier_aging_rows, _ = build_aging_rows(supplier_aging_invoices, supplier_settlements)
        overdue_supplier_invoices = sum(1 for row in supplier_aging_rows if sum(row[3:7]) > 0)

        conn.close()
        return render_template(
            "dashboard.html",
            entries=entries,
            accounts_count=accounts_count,
            total=total,
            products_count=products_count,
            inventory_value=inventory_value,
            low_stock_count=low_stock_count,
            sales_total=sales_total,
            purchases_total=purchases_total,
            customer_balance_total=customer_balance_total,
            supplier_balance_total=supplier_balance_total,
            overdue_customer_invoices=overdue_customer_invoices,
            overdue_supplier_invoices=overdue_supplier_invoices,
            customers_count=customers_count,
            suppliers_count=suppliers_count,
            receipts_total=receipts_total,
            payments_total=payments_total,
            net_cash_movement=net_cash_movement,
            sales_orders_count=sales_orders_count,
            purchase_orders_count=purchase_orders_count,
            delivery_notes_count=delivery_notes_count,
            receipt_notes_count=receipt_notes_count,
        )

    return dashboard


def build_company_settings_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    default_tax_rate = deps["DEFAULT_TAX_RATE"]
    row_snapshot = deps["row_snapshot"]
    log_action = deps["log_action"]
    get_company_settings = deps["get_company_settings"]
    upload_dir = deps["UPLOAD_DIR"]
    logo_extensions = deps["LOGO_EXTENSIONS"]
    max_logo_size = deps["MAX_LOGO_SIZE"]

    def company_settings():
        conn = db()
        cur = conn.cursor()

        if request.method == "POST":
            data = {
                "company_name": request.form.get("company_name", "").strip(),
                "tax_number": request.form.get("tax_number", "").strip(),
                "commercial_register": request.form.get("commercial_register", "").strip(),
                "address": request.form.get("address", "").strip(),
                "phone": request.form.get("phone", "").strip(),
                "email": request.form.get("email", "").strip(),
                "default_tax_rate": parse_positive_amount(request.form.get("default_tax_rate", default_tax_rate)),
                "invoice_footer": request.form.get("invoice_footer", "").strip(),
            }
            uploaded_logo = request.files.get("company_logo")
            if not data["company_name"]:
                flash("اسم الشركة مطلوب.", "danger")
            else:
                current_settings = get_company_settings(cur)
                logo_path = current_settings.get("logo_path", "")
                if uploaded_logo and uploaded_logo.filename:
                    _, ext = os.path.splitext(uploaded_logo.filename.lower())
                    if ext not in logo_extensions:
                        flash("امتداد الشعار غير مدعوم. استخدم PNG أو JPG أو JPEG.", "danger")
                        conn.close()
                        return redirect(url_for("company_settings"))
                    uploaded_logo.stream.seek(0, os.SEEK_END)
                    file_size = uploaded_logo.stream.tell()
                    uploaded_logo.stream.seek(0)
                    if file_size > max_logo_size:
                        flash("حجم الشعار يجب ألا يتجاوز 2 ميجابايت.", "danger")
                        conn.close()
                        return redirect(url_for("company_settings"))
                    os.makedirs(upload_dir, exist_ok=True)
                    saved_name = f"company-logo{ext}"
                    uploaded_logo.save(os.path.join(upload_dir, saved_name))
                    logo_path = f"/static/uploads/{saved_name}"

                before = row_snapshot(cur, "company_settings", 1)
                cur.execute(
                    """
                    UPDATE company_settings
                    SET company_name=?, tax_number=?, commercial_register=?, address=?,
                        phone=?, email=?, logo_path=?, default_tax_rate=?, invoice_footer=?
                    WHERE id=1
                    """,
                    (
                        data["company_name"],
                        data["tax_number"],
                        data["commercial_register"],
                        data["address"],
                        data["phone"],
                        data["email"],
                        logo_path,
                        data["default_tax_rate"],
                        data["invoice_footer"],
                    ),
                )
                after = row_snapshot(cur, "company_settings", 1)
                log_action(cur, "update", "company_settings", 1, "تحديث بيانات الشركة", before, after)
                conn.commit()
                flash("تم حفظ إعدادات الشركة.", "success")

        settings = get_company_settings(cur)
        conn.close()
        return render_template("company_settings.html", settings=settings)

    return company_settings


def build_posting_control_view(deps):
    db = deps["db"]
    posting_groups = deps["POSTING_GROUPS"]
    ensure_posting_rows = deps["ensure_posting_rows"]

    def posting_control():
        conn = db()
        cur = conn.cursor()
        ensure_posting_rows(cur)
        rows = []
        for group_key, info in posting_groups.items():
            table = info["table"]
            if group_key == "manual_journal":
                cur.execute(
                    """
                    SELECT
                        COALESCE(SUM(CASE WHEN status='posted' AND source_type='manual' THEN 1 ELSE 0 END),0),
                        COALESCE(SUM(CASE WHEN status='draft' AND source_type='manual' THEN 1 ELSE 0 END),0)
                    FROM journal
                    """
                )
            else:
                cur.execute(
                    f"""
                    SELECT
                        COALESCE(SUM(CASE WHEN status='posted' THEN 1 ELSE 0 END),0),
                        COALESCE(SUM(CASE WHEN status='draft' THEN 1 ELSE 0 END),0)
                    FROM {table}
                    """
                )
            posted_count, draft_count = cur.fetchone()
            cur.execute(
                """
                SELECT is_posted,posted_at,posted_by,unposted_at,unposted_by
                FROM posting_control
                WHERE group_key=?
                """,
                (group_key,),
            )
            state = cur.fetchone()
            rows.append(
                {
                    "key": group_key,
                    "name": info["name"],
                    "is_posted": bool(state[0]) if state else True,
                    "posted_count": posted_count,
                    "draft_count": draft_count,
                    "posted_at": state[1] if state else "",
                    "posted_by": state[2] if state else "",
                    "unposted_at": state[3] if state else "",
                    "unposted_by": state[4] if state else "",
                    "list_endpoint": info["list_endpoint"],
                }
            )
        conn.commit()
        conn.close()
        return render_template("posting_control.html", rows=rows)

    return posting_control


def build_posting_control_action_view(deps):
    db = deps["db"]
    posting_groups = deps["POSTING_GROUPS"]
    ensure_posting_rows = deps["ensure_posting_rows"]
    post_group = deps["post_group"]
    unpost_group = deps["unpost_group"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]

    def posting_control_action(group_key, action):
        if group_key not in posting_groups or action not in ("post", "unpost"):
            flash("طلب ترحيل غير صحيح.", "danger")
            return redirect(url_for("posting_control"))

        conn = db()
        cur = conn.cursor()
        ensure_posting_rows(cur)
        try:
            if action == "post":
                post_group(cur, group_key)
                cur.execute(
                    """
                    UPDATE posting_control
                    SET is_posted=1, posted_at=CURRENT_TIMESTAMP, posted_by=?
                    WHERE group_key=?
                    """,
                    (session.get("username", ""), group_key),
                )
                log_action(cur, "post", "posting_group", None, group_key)
                message = f"تم ترحيل مجموعة {posting_groups[group_key]['name']}."
            else:
                unpost_group(cur, group_key)
                cur.execute(
                    """
                    UPDATE posting_control
                    SET is_posted=0, unposted_at=CURRENT_TIMESTAMP, unposted_by=?
                    WHERE group_key=?
                    """,
                    (session.get("username", ""), group_key),
                )
                log_action(cur, "unpost", "posting_group", None, group_key)
                message = f"تم فك ترحيل مجموعة {posting_groups[group_key]['name']} ويمكن تعديل عملياتها."
            conn.commit()
            rebuild_ledger()
            flash(message, "success")
        except ValueError as exc:
            conn.rollback()
            flash(str(exc), "danger")
        finally:
            conn.close()

        return redirect(url_for("posting_control"))

    return posting_control_action


def build_fiscal_periods_view(deps):
    db = deps["db"]
    log_action = deps["log_action"]

    def fiscal_periods():
        conn = db()
        cur = conn.cursor()

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            start_date = request.form.get("start_date", "").strip()
            end_date = request.form.get("end_date", "").strip()
            notes = request.form.get("notes", "").strip()

            if not name or not start_date or not end_date:
                flash("اسم الفترة وتاريخ البداية والنهاية مطلوبان.", "danger")
            elif start_date > end_date:
                flash("تاريخ بداية الفترة لا يمكن أن يكون بعد تاريخ النهاية.", "danger")
            else:
                cur.execute(
                    """
                    SELECT name
                    FROM fiscal_periods
                    WHERE NOT (? < start_date OR ? > end_date)
                    LIMIT 1
                    """,
                    (end_date, start_date),
                )
                overlap = cur.fetchone()
                if overlap:
                    flash(f"هذه الفترة تتداخل مع الفترة {overlap[0]}.", "danger")
                else:
                    cur.execute(
                        """
                        INSERT INTO fiscal_periods(name,start_date,end_date,notes)
                        VALUES (?,?,?,?)
                        """,
                        (name, start_date, end_date, notes),
                    )
                    period_id = cur.lastrowid
                    log_action(cur, "create", "fiscal_period", period_id, name)
                    conn.commit()
                    flash("تم إنشاء الفترة المالية.", "success")
                    return redirect(url_for("fiscal_periods"))

        cur.execute(
            """
            SELECT id,name,start_date,end_date,status,closed_at,closed_by,reopened_at,reopened_by,notes
            FROM fiscal_periods
            ORDER BY start_date DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("fiscal_periods.html", rows=rows)

    return fiscal_periods


def build_fiscal_period_action_view(deps):
    db = deps["db"]
    log_action = deps["log_action"]

    def fiscal_period_action(id, action):
        if action not in ("close", "open"):
            flash("إجراء الفترة المالية غير صحيح.", "danger")
            return redirect(url_for("fiscal_periods"))

        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT name,status FROM fiscal_periods WHERE id=?", (id,))
        period = cur.fetchone()
        if not period:
            conn.close()
            flash("الفترة المالية غير موجودة.", "danger")
            return redirect(url_for("fiscal_periods"))

        if action == "close":
            cur.execute(
                """
                UPDATE fiscal_periods
                SET status='closed', closed_at=CURRENT_TIMESTAMP, closed_by=?
                WHERE id=?
                """,
                (session.get("username", ""), id),
            )
            log_action(cur, "close", "fiscal_period", id, period[0])
            flash("تم إقفال الفترة المالية.", "success")
        else:
            if session.get("role") != "admin":
                conn.close()
                flash("فتح الفترة المالية المغلقة متاح للمدير فقط.", "danger")
                return redirect(url_for("fiscal_periods"))
            cur.execute(
                """
                UPDATE fiscal_periods
                SET status='open', reopened_at=CURRENT_TIMESTAMP, reopened_by=?
                WHERE id=?
                """,
                (session.get("username", ""), id),
            )
            log_action(cur, "reopen", "fiscal_period", id, period[0])
            flash("تم فتح الفترة المالية المغلقة.", "success")

        conn.commit()
        conn.close()
        return redirect(url_for("fiscal_periods"))

    return fiscal_period_action
