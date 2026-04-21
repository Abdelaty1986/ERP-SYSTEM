from flask import flash, redirect, render_template, request, url_for


def build_accounts_view(deps):
    db = deps["db"]
    validate_account_form = deps["validate_account_form"]
    account_types = deps["ACCOUNT_TYPES"]

    def accounts():
        conn = db()
        cur = conn.cursor()

        if request.method == "POST":
            errors, data = validate_account_form(cur, request.form)
            if errors:
                for error in errors:
                    flash(error, "danger")
            else:
                cur.execute(
                    "INSERT INTO accounts(code,name,type) VALUES (?,?,?)",
                    (data["code"], data["name"], data["type"]),
                )
                conn.commit()
                conn.close()
                flash("تم إضافة الحساب بنجاح.", "success")
                return redirect(url_for("accounts"))

        cur.execute(
            """
            SELECT a.id, a.code, a.name, a.type, COUNT(j.id) AS journal_count
            FROM accounts a
            LEFT JOIN journal j
                ON a.id = j.debit_account_id OR a.id = j.credit_account_id
            GROUP BY a.id
            ORDER BY a.code
            """
        )
        accounts_rows = cur.fetchall()
        conn.close()
        return render_template("accounts.html", accounts=accounts_rows, account_types=account_types)

    return accounts


def build_account_edit_view(deps):
    db = deps["db"]
    validate_account_form = deps["validate_account_form"]
    row_snapshot = deps["row_snapshot"]
    log_action = deps["log_action"]
    account_types = deps["ACCOUNT_TYPES"]

    def account_edit(id):
        conn = db()
        cur = conn.cursor()

        cur.execute("SELECT id, code, name, type FROM accounts WHERE id=?", (id,))
        account = cur.fetchone()
        if not account:
            conn.close()
            flash("الحساب غير موجود.", "danger")
            return redirect(url_for("accounts"))

        if request.method == "POST":
            errors, data = validate_account_form(cur, request.form, current_id=id)
            if errors:
                for error in errors:
                    flash(error, "danger")
            else:
                before = row_snapshot(cur, "accounts", id)
                cur.execute(
                    "UPDATE accounts SET code=?, name=?, type=? WHERE id=?",
                    (data["code"], data["name"], data["type"], id),
                )
                after = row_snapshot(cur, "accounts", id)
                log_action(cur, "update", "account", id, "تعديل حساب", before, after)
                conn.commit()
                conn.close()
                flash("تم تعديل الحساب بنجاح.", "success")
                return redirect(url_for("accounts"))

        conn.close()
        return render_template("account_form.html", account=account, account_types=account_types)

    return account_edit


def build_account_delete_view(deps):
    db = deps["db"]
    row_snapshot = deps["row_snapshot"]
    log_action = deps["log_action"]

    def account_delete(id):
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*)
            FROM journal
            WHERE debit_account_id=? OR credit_account_id=?
            """,
            (id, id),
        )
        journal_count = cur.fetchone()[0]
        if journal_count:
            conn.close()
            flash("لا يمكن حذف حساب مستخدم في قيود يومية.", "danger")
            return redirect(url_for("accounts"))

        before = row_snapshot(cur, "accounts", id)
        cur.execute("DELETE FROM accounts WHERE id=?", (id,))
        log_action(cur, "delete", "account", id, "حذف حساب", before, None)
        conn.commit()
        conn.close()
        flash("تم حذف الحساب.", "success")
        return redirect(url_for("accounts"))

    return account_delete


def build_journal_view(deps):
    db = deps["db"]
    validate_journal_form = deps["validate_journal_form"]
    ensure_open_period = deps["ensure_open_period"]
    is_group_posted = deps["is_group_posted"]
    rebuild_ledger = deps["rebuild_ledger"]

    def journal():
        conn = db()
        cur = conn.cursor()

        if request.method == "POST":
            errors, data = validate_journal_form(cur, request.form)
            if errors:
                for error in errors:
                    flash(error, "danger")
            else:
                try:
                    ensure_open_period(cur, data["date"])
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("journal"))
                journal_status = "posted" if is_group_posted(cur, "manual_journal") else "draft"
                cur.execute(
                    """
                    INSERT INTO journal(date,description,debit_account_id,credit_account_id,amount,status,source_type,cost_center_id)
                    VALUES (?,?,?,?,?,?, 'manual',?)
                    """,
                    (
                        data["date"],
                        data["description"],
                        data["debit"],
                        data["credit"],
                        data["amount"],
                        journal_status,
                        data["cost_center_id"],
                    ),
                )
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash("تم حفظ القيد بنجاح.", "success")
                return redirect(url_for("journal"))

        cur.execute(
            """
            SELECT j.id,j.date,j.description,
                   a1.name,
                   a2.name,
                   j.amount,
                   j.status,
                   COALESCE(cc.name,'')
            FROM journal j
            JOIN accounts a1 ON j.debit_account_id=a1.id
            JOIN accounts a2 ON j.credit_account_id=a2.id
            LEFT JOIN cost_centers cc ON j.cost_center_id=cc.id
            ORDER BY j.id DESC
            """
        )
        journal_rows = cur.fetchall()
        cur.execute("SELECT id, code, name FROM accounts ORDER BY name")
        accounts_rows = cur.fetchall()
        cur.execute("SELECT id, code, name FROM cost_centers WHERE status='active' ORDER BY code,name")
        cost_centers = cur.fetchall()
        group_posted = is_group_posted(cur, "manual_journal")
        conn.commit()
        conn.close()
        return render_template("journal.html", journal=journal_rows, accounts=accounts_rows, cost_centers=cost_centers, group_posted=group_posted)

    return journal


def build_journal_export_view(deps):
    db = deps["db"]
    excel_response = deps["excel_response"]

    def journal_export():
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT j.id,j.date,j.description,a1.name,a2.name,j.amount
            FROM journal j
            JOIN accounts a1 ON j.debit_account_id=a1.id
            JOIN accounts a2 ON j.credit_account_id=a2.id
            ORDER BY j.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return excel_response("journal.xls", ["رقم القيد", "التاريخ", "البيان", "مدين", "دائن", "المبلغ"], rows, title="القيود اليومية")

    return journal_export


def build_edit_journal_view(deps):
    db = deps["db"]
    validate_journal_form = deps["validate_journal_form"]
    rebuild_ledger = deps["rebuild_ledger"]

    def edit(id):
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id,date,description,debit_account_id,credit_account_id,amount,status,source_type
            FROM journal
            WHERE id=?
            """,
            (id,),
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            flash("القيد غير موجود.", "danger")
            return redirect(url_for("journal"))
        if row[6] == "posted":
            conn.close()
            flash("لا يمكن تعديل قيد مرحل. فك ترحيل مجموعة القيود اليومية أولًا.", "danger")
            return redirect(url_for("journal"))
        if row[7] != "manual":
            conn.close()
            flash("لا يمكن تعديل قيد آلي مباشرة. عدل المستند المرتبط بعد فك ترحيله.", "danger")
            return redirect(url_for("journal"))

        if request.method == "POST":
            errors, data = validate_journal_form(cur, request.form)
            if errors:
                for error in errors:
                    flash(error, "danger")
            else:
                cur.execute(
                    """
                    UPDATE journal
                    SET date=?,description=?,debit_account_id=?,credit_account_id=?,amount=?
                    WHERE id=?
                    """,
                    (
                        data["date"],
                        data["description"],
                        data["debit"],
                        data["credit"],
                        data["amount"],
                        id,
                    ),
                )
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash("تم تعديل القيد بنجاح.", "success")
                return redirect(url_for("journal"))

        cur.execute("SELECT id, code, name FROM accounts ORDER BY name")
        accounts_rows = cur.fetchall()
        conn.close()
        return render_template("edit.html", row=row, accounts=accounts_rows)

    return edit


def build_delete_journal_view(deps):
    db = deps["db"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]

    def delete(id):
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT status,source_type FROM journal WHERE id=?", (id,))
        row = cur.fetchone()
        if row and row[0] == "draft" and row[1] == "manual":
            cur.execute("DELETE FROM journal WHERE id=?", (id,))
            log_action(cur, "delete", "journal", id, "حذف قيد غير مرحل")
            conn.commit()
            conn.close()
            rebuild_ledger()
            flash("تم حذف القيد غير المرحل.", "success")
            return redirect(url_for("journal"))
        conn.close()
        flash("لا يمكن حذف القيود المرحلة. استخدم قيد عكسي أو فك الترحيل أولًا.", "danger")
        return redirect(url_for("journal"))

    return delete


def build_ledger_view(deps):
    db = deps["db"]

    def ledger(id):
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM accounts WHERE id=?", (id,))
        account = cur.fetchone()
        if not account:
            conn.close()
            flash("الحساب غير موجود.", "danger")
            return redirect(url_for("accounts"))
        cur.execute(
            """
            SELECT date,description,debit,credit
            FROM ledger
            WHERE account_id=?
            ORDER BY id
            """,
            (id,),
        )
        rows = cur.fetchall()
        debit = sum(r[2] for r in rows)
        credit = sum(r[3] for r in rows)
        balance = debit - credit
        conn.close()
        return render_template("ledger.html", account_id=account[0], acc_name=account[1], rows=rows, debit=debit, credit=credit, balance=balance)

    return ledger


def build_ledger_export_view(deps):
    db = deps["db"]
    excel_response = deps["excel_response"]

    def ledger_export(id):
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT name FROM accounts WHERE id=?", (id,))
        account = cur.fetchone()
        if not account:
            conn.close()
            flash("الحساب غير موجود.", "danger")
            return redirect(url_for("accounts"))
        cur.execute(
            """
            SELECT date,description,debit,credit
            FROM ledger
            WHERE account_id=?
            ORDER BY id
            """,
            (id,),
        )
        rows = cur.fetchall()
        conn.close()
        return excel_response(f"ledger-{id}.xls", ["التاريخ", "البيان", "مدين", "دائن"], rows, title="دفتر الأستاذ")

    return ledger_export


def build_trial_view(deps):
    db = deps["db"]

    def trial():
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT a.name,
                   COALESCE(SUM(l.debit),0),
                   COALESCE(SUM(l.credit),0)
            FROM accounts a
            LEFT JOIN ledger l ON a.id = l.account_id
            GROUP BY a.id
            ORDER BY a.code
            """
        )
        data = cur.fetchall()
        total_debit = sum(row[1] for row in data)
        total_credit = sum(row[2] for row in data)
        conn.close()
        return render_template("trial_balance.html", data=data, total_debit=total_debit, total_credit=total_credit)

    return trial


def build_trial_export_view(deps):
    db = deps["db"]
    excel_response = deps["excel_response"]

    def trial_export():
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT a.name,
                   COALESCE(SUM(l.debit),0),
                   COALESCE(SUM(l.credit),0)
            FROM accounts a
            LEFT JOIN ledger l ON a.id = l.account_id
            GROUP BY a.id
            ORDER BY a.code
            """
        )
        rows = cur.fetchall()
        conn.close()
        return excel_response("trial-balance.xls", ["الحساب", "مدين", "دائن"], rows, title="ميزان المراجعة")

    return trial_export
