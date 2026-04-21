from flask import flash, redirect, render_template, request, url_for


def _account_balances_by_type(cur, account_type):
    cur.execute(
        """
        SELECT a.code,a.name,
               COALESCE(SUM(l.debit),0) AS debit,
               COALESCE(SUM(l.credit),0) AS credit
        FROM accounts a
        LEFT JOIN ledger l ON l.account_id=a.id
        WHERE a.type=?
        GROUP BY a.id
        ORDER BY a.code
        """,
        (account_type,),
    )
    return cur.fetchall()


def _debit_balance_rows(rows):
    result = []
    for code, name, debit, credit in rows:
        amount = (debit or 0) - (credit or 0)
        if abs(amount) > 0.0001:
            result.append((code, name, amount))
    return result


def _credit_balance_rows(rows):
    result = []
    for code, name, debit, credit in rows:
        amount = (credit or 0) - (debit or 0)
        if abs(amount) > 0.0001:
            result.append((code, name, amount))
    return result


def build_balance_sheet_report_view(deps):
    db = deps["db"]

    def balance_sheet_report():
        conn = db()
        cur = conn.cursor()
        assets = _debit_balance_rows(_account_balances_by_type(cur, "أصول"))
        liabilities = _credit_balance_rows(_account_balances_by_type(cur, "خصوم"))
        equity = _credit_balance_rows(_account_balances_by_type(cur, "حقوق ملكية"))
        revenue_total = sum(row[2] for row in _credit_balance_rows(_account_balances_by_type(cur, "إيرادات")))
        expense_total = sum(row[2] for row in _debit_balance_rows(_account_balances_by_type(cur, "مصروفات")))
        net_income = revenue_total - expense_total
        if abs(net_income) > 0.0001:
            equity.append(("3400", "صافي ربح أو خسارة الفترة", net_income))
        total_assets = sum(row[2] for row in assets)
        total_liabilities = sum(row[2] for row in liabilities)
        total_equity = sum(row[2] for row in equity)
        conn.close()
        return render_template(
            "balance_sheet.html",
            assets=assets,
            liabilities=liabilities,
            equity=equity,
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            total_equity=total_equity,
            difference=total_assets - (total_liabilities + total_equity),
        )

    return balance_sheet_report


def build_cash_flow_report_view(deps):
    db = deps["db"]

    def cash_flow_report():
        conn = db()
        cur = conn.cursor()
        cash_codes = ("1100", "1110", "1120", "1200", "1210")
        placeholders = ",".join(["?"] * len(cash_codes))
        cur.execute(
            f"""
            SELECT j.date,j.description,da.code,da.name,ca.code,ca.name,j.amount
            FROM journal j
            JOIN accounts da ON da.id=j.debit_account_id
            JOIN accounts ca ON ca.id=j.credit_account_id
            WHERE j.status='posted'
              AND (da.code IN ({placeholders}) OR ca.code IN ({placeholders}))
            ORDER BY j.date,j.id
            """,
            (*cash_codes, *cash_codes),
        )
        rows = []
        totals = {"operating": 0, "investing": 0, "financing": 0}
        for date_value, desc, debit_code, debit_name, credit_code, credit_name, amount in cur.fetchall():
            if debit_code in cash_codes:
                direction = "in"
                other_code = credit_code
                other_name = credit_name
                signed_amount = amount
            else:
                direction = "out"
                other_code = debit_code
                other_name = debit_name
                signed_amount = -amount

            if other_code.startswith("18") or other_code.startswith("145"):
                activity = "investing"
                activity_label = "استثمارية"
            elif other_code.startswith("24") or other_code.startswith("25") or other_code.startswith("3"):
                activity = "financing"
                activity_label = "تمويلية"
            else:
                activity = "operating"
                activity_label = "تشغيلية"
            totals[activity] += signed_amount
            rows.append((date_value, desc, activity_label, other_code, other_name, direction, amount, signed_amount))

        cur.execute(
            f"""
            SELECT COALESCE(SUM(l.debit),0)-COALESCE(SUM(l.credit),0)
            FROM ledger l
            JOIN accounts a ON a.id=l.account_id
            WHERE a.code IN ({placeholders})
            """,
            cash_codes,
        )
        ending_cash = cur.fetchone()[0]
        net_cash_flow = sum(totals.values())
        beginning_cash = ending_cash - net_cash_flow
        conn.close()
        return render_template(
            "cash_flow.html",
            rows=rows,
            totals=totals,
            beginning_cash=beginning_cash,
            net_cash_flow=net_cash_flow,
            ending_cash=ending_cash,
        )

    return cash_flow_report


def build_cost_center_report_view(deps):
    db = deps["db"]

    def cost_center_report():
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            WITH lines AS (
                SELECT cc.code AS center_code,cc.name AS center_name,a.type AS account_type,
                       j.amount AS debit,0 AS credit
                FROM journal j
                JOIN cost_centers cc ON cc.id=j.cost_center_id
                JOIN accounts a ON a.id=j.debit_account_id
                WHERE j.status='posted'
                UNION ALL
                SELECT cc.code AS center_code,cc.name AS center_name,a.type AS account_type,
                       0 AS debit,j.amount AS credit
                FROM journal j
                JOIN cost_centers cc ON cc.id=j.cost_center_id
                JOIN accounts a ON a.id=j.credit_account_id
                WHERE j.status='posted'
            )
            SELECT center_code,center_name,
                   SUM(CASE WHEN account_type='إيرادات' THEN credit-debit ELSE 0 END) AS revenue,
                   SUM(CASE WHEN account_type='مصروفات' THEN debit-credit ELSE 0 END) AS expense
            FROM lines
            GROUP BY center_code,center_name
            ORDER BY center_code,center_name
            """
        )
        rows = cur.fetchall()
        totals = {"revenue": sum(row[2] or 0 for row in rows), "expense": sum(row[3] or 0 for row in rows)}
        conn.close()
        return render_template("cost_center_report.html", rows=rows, totals=totals)

    return cost_center_report


def build_opening_balances_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    get_account_id = deps["get_account_id"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]

    def opening_balances():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            account_id = request.form.get("account_id")
            side = request.form.get("side", "debit")
            amount = parse_positive_amount(request.form.get("amount"))
            notes = request.form.get("notes", "").strip()
            if not date_value or not account_id or amount <= 0 or side not in ("debit", "credit"):
                flash("راجع بيانات الرصيد الافتتاحي.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("opening_balances"))
                opening_id = get_account_id(cur, "1900")
                if side == "debit":
                    debit_id, credit_id = account_id, opening_id
                else:
                    debit_id, credit_id = opening_id, account_id
                cur.execute(
                    """
                    INSERT INTO journal(date,description,debit_account_id,credit_account_id,amount,status,source_type)
                    VALUES (?,?,?,?,?,'posted','opening')
                    """,
                    (date_value, f"رصيد افتتاحي - {notes}", debit_id, credit_id, amount),
                )
                journal_id = cur.lastrowid
                log_action(cur, "create", "opening_balance", journal_id, f"amount={amount}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash("تم تسجيل الرصيد الافتتاحي.", "success")
                return redirect(url_for("opening_balances"))
        cur.execute("SELECT id,code,name,type FROM accounts ORDER BY code")
        accounts_rows = cur.fetchall()
        cur.execute(
            """
            SELECT j.date,j.description,a1.name,a2.name,j.amount
            FROM journal j
            JOIN accounts a1 ON a1.id=j.debit_account_id
            JOIN accounts a2 ON a2.id=j.credit_account_id
            WHERE j.source_type='opening'
            ORDER BY j.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("opening_balances.html", accounts=accounts_rows, rows=rows)

    return opening_balances


def build_year_end_view(deps):
    db = deps["db"]
    ensure_open_period = deps["ensure_open_period"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]

    def year_end():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            fiscal_year = request.form.get("fiscal_year", "").strip()
            closing_date = request.form.get("closing_date", "").strip()
            notes = request.form.get("notes", "").strip()
            if not fiscal_year or not closing_date:
                flash("السنة وتاريخ الإقفال مطلوبان.", "danger")
            else:
                cur.execute("SELECT id FROM year_end_closings WHERE fiscal_year=?", (fiscal_year,))
                if cur.fetchone():
                    flash("تم إقفال هذه السنة من قبل.", "danger")
                else:
                    try:
                        ensure_open_period(cur, closing_date)
                    except ValueError as exc:
                        flash(str(exc), "danger")
                        conn.close()
                        return redirect(url_for("year_end"))
                    revenue_rows = _account_balances_by_type(cur, "إيرادات")
                    expense_rows = _account_balances_by_type(cur, "مصروفات")
                    revenue_total = 0
                    expense_total = 0
                    closing_journal_ids = []

                    for code, name, debit, credit in revenue_rows:
                        amount = (credit or 0) - (debit or 0)
                        revenue_total += amount
                        if abs(amount) <= 0.0001:
                            continue
                        if amount > 0:
                            closing_journal_ids.append(create_auto_journal(cur, closing_date, f"إقفال إيراد {name} - {fiscal_year}", code, "3400", amount))
                        else:
                            closing_journal_ids.append(create_auto_journal(cur, closing_date, f"إقفال مردود/خصم {name} - {fiscal_year}", "3400", code, abs(amount)))

                    for code, name, debit, credit in expense_rows:
                        amount = (debit or 0) - (credit or 0)
                        expense_total += amount
                        if abs(amount) <= 0.0001:
                            continue
                        if amount > 0:
                            closing_journal_ids.append(create_auto_journal(cur, closing_date, f"إقفال مصروف {name} - {fiscal_year}", "3400", code, amount))
                        else:
                            closing_journal_ids.append(create_auto_journal(cur, closing_date, f"إقفال عكس مصروف {name} - {fiscal_year}", code, "3400", abs(amount)))

                    net_income = revenue_total - expense_total
                    if abs(net_income) < 0.0001:
                        journal_id = None
                    elif net_income > 0:
                        journal_id = create_auto_journal(cur, closing_date, f"ترحيل صافي ربح {fiscal_year}", "3400", "3500", net_income)
                        closing_journal_ids.append(journal_id)
                    else:
                        journal_id = create_auto_journal(cur, closing_date, f"ترحيل صافي خسارة {fiscal_year}", "3500", "3400", abs(net_income))
                        closing_journal_ids.append(journal_id)
                    cur.execute(
                        """
                        INSERT INTO year_end_closings(fiscal_year,closing_date,revenue_total,expense_total,net_income,journal_id,notes)
                        VALUES (?,?,?,?,?,?,?)
                        """,
                        (fiscal_year, closing_date, revenue_total, expense_total, net_income, journal_id, notes),
                    )
                    closing_id = cur.lastrowid
                    mark_journal_source(cur, "year_end", closing_id, *closing_journal_ids)
                    log_action(cur, "close", "year_end", closing_id, fiscal_year)
                    conn.commit()
                    conn.close()
                    rebuild_ledger()
                    flash("تم تنفيذ قيود إقفال السنة وترحيل النتيجة.", "success")
                    return redirect(url_for("year_end"))
        cur.execute("SELECT id,fiscal_year,closing_date,revenue_total,expense_total,net_income,status FROM year_end_closings ORDER BY fiscal_year DESC")
        rows = cur.fetchall()
        conn.close()
        return render_template("year_end.html", rows=rows)

    return year_end


def build_profit_loss_report_view(deps):
    db = deps["db"]

    def profit_loss_report():
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(total),0), COALESCE(SUM(cost_total),0) FROM sales_invoices WHERE status='posted'")
        sales_total, cost_total = cur.fetchone()
        cur.execute("SELECT COALESCE(SUM(amount),0) FROM financial_sales_invoices WHERE status='posted'")
        sales_total += cur.fetchone()[0]
        cur.execute("SELECT COALESCE(SUM(total),0) FROM purchase_invoices WHERE status='posted'")
        purchases_total = cur.fetchone()[0]
        cur.execute(
            """
            SELECT a.name, COALESCE(SUM(l.debit),0) - COALESCE(SUM(l.credit),0) AS amount
            FROM accounts a
            LEFT JOIN ledger l ON a.id=l.account_id
            WHERE a.type='مصروفات' AND a.code <> '6100'
            GROUP BY a.id
            ORDER BY a.code
            """
        )
        expense_rows = cur.fetchall()
        expenses_total = sum(row[1] for row in expense_rows)
        gross_profit = sales_total - cost_total
        net_profit = gross_profit - expenses_total
        conn.close()
        return render_template(
            "profit_loss.html",
            sales_total=sales_total,
            cost_total=cost_total,
            purchases_total=purchases_total,
            gross_profit=gross_profit,
            expense_rows=expense_rows,
            expenses_total=expenses_total,
            net_profit=net_profit,
        )

    return profit_loss_report


def build_vat_report_view(deps):
    db = deps["db"]

    def vat_report():
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                (SELECT COALESCE(SUM(tax_amount),0) FROM sales_invoices WHERE status='posted') +
                (SELECT COALESCE(SUM(tax_amount),0) FROM financial_sales_invoices WHERE status='posted')
            """
        )
        output_vat = cur.fetchone()[0]
        cur.execute("SELECT COALESCE(SUM(tax_amount),0) FROM purchase_invoices WHERE status='posted'")
        input_vat = cur.fetchone()[0]
        payable_vat = output_vat - input_vat
        cur.execute(
            """
            SELECT date,'مبيعات' AS source,id,total,tax_amount,grand_total
            FROM sales_invoices
            WHERE tax_amount > 0 AND status='posted'
            UNION ALL
            SELECT date,'مبيعات مالية' AS source,id,amount,tax_amount,grand_total
            FROM financial_sales_invoices
            WHERE tax_amount > 0 AND status='posted'
            UNION ALL
            SELECT date,'مشتريات' AS source,id,total,tax_amount,grand_total
            FROM purchase_invoices
            WHERE tax_amount > 0 AND status='posted'
            ORDER BY date DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("vat_report.html", output_vat=output_vat, input_vat=input_vat, payable_vat=payable_vat, rows=rows)

    return vat_report
