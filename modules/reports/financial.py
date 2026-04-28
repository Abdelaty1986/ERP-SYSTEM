from flask import render_template_string, request
from io import BytesIO

from flask import flash, redirect, render_template, request, send_file, url_for
from openpyxl import Workbook
from openpyxl.styles import Font


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


def _tax_report_excel(filename, title, rows, total_label, total_value):
    wb = Workbook()
    ws = wb.active
    ws.title = "Report"
    ws.sheet_view.rightToLeft = True
    ws["A1"] = title
    ws["A1"].font = Font(bold=True)
    headers = ["التاريخ", "رقم الفاتورة", "الجهة", "الصنف", "الوحدة", "قيمة الصنف", "النسبة", "الضريبة", "النوع", "الإجمالي"]
    for idx, header in enumerate(headers, start=1):
        ws.cell(row=3, column=idx, value=header).font = Font(bold=True)
    row_idx = 3
    for row in rows:
        row_idx += 1
        for idx, value in enumerate(row, start=1):
            ws.cell(row=row_idx, column=idx, value=value)
    ws.cell(row=row_idx + 2, column=1, value=total_label).font = Font(bold=True)
    ws.cell(row=row_idx + 2, column=2, value=total_value)
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


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
        date_from = request.args.get("date_from", "").strip()
        date_to = request.args.get("date_to", "").strip()

        where_sales = ["s.status='posted'"]
        where_purchases = ["p.status='posted'"]
        params_sales = []
        params_purchases = []

        if date_from:
            where_sales.append("s.date >= ?")
            where_purchases.append("p.date >= ?")
            params_sales.append(date_from)
            params_purchases.append(date_from)

        if date_to:
            where_sales.append("s.date <= ?")
            where_purchases.append("p.date <= ?")
            params_sales.append(date_to)
            params_purchases.append(date_to)

        sales_where_sql = " AND ".join(where_sales)
        purchases_where_sql = " AND ".join(where_purchases)

        conn = db()
        cur = conn.cursor()

        cur.execute(f"""
            SELECT
                s.date,
                'مبيعات' AS doc_type,
                COALESCE(s.doc_no, 'SI-' || printf('%06d', s.id)) AS doc_no,
                COALESCE(c.name, 'عميل نقدي') AS party_name,
                COALESCE(p.name, '') AS item_name,
                COALESCE(l.total, 0) AS net_amount,
                COALESCE(l.vat_amount, 0) AS vat_amount,
                (COALESCE(l.total,0) + COALESCE(l.vat_amount,0) - COALESCE(l.withholding_amount,0)) AS grand_total
            FROM sales_invoices s
            JOIN sales_invoice_lines l ON l.invoice_id = s.id
            LEFT JOIN products p ON p.id = l.product_id
            LEFT JOIN customers c ON c.id = s.customer_id
            WHERE {sales_where_sql} AND COALESCE(l.vat_amount,0) > 0

            UNION ALL

            SELECT
                s.date,
                'مبيعات' AS doc_type,
                COALESCE(s.doc_no, 'SI-' || printf('%06d', s.id)) AS doc_no,
                COALESCE(c.name, 'عميل نقدي') AS party_name,
                COALESCE(p.name, '') AS item_name,
                COALESCE(s.total, 0) AS net_amount,
                COALESCE(s.tax_amount, 0) AS vat_amount,
                (COALESCE(s.total,0) + COALESCE(s.tax_amount,0) - COALESCE(s.withholding_amount,0)) AS grand_total
            FROM sales_invoices s
            LEFT JOIN products p ON p.id = s.product_id
            LEFT JOIN customers c ON c.id = s.customer_id
            WHERE {sales_where_sql}
              AND NOT EXISTS (SELECT 1 FROM sales_invoice_lines l2 WHERE l2.invoice_id=s.id)
              AND COALESCE(s.tax_amount,0) > 0
        """, params_sales + params_sales)

        sales_rows = cur.fetchall()

        cur.execute(f"""
            SELECT
                p.date,
                'مشتريات' AS doc_type,
                COALESCE(p.doc_no, p.supplier_invoice_no, 'PI-' || printf('%06d', p.id)) AS doc_no,
                COALESCE(s.name, 'مورد نقدي') AS party_name,
                COALESCE(pr.name, '') AS item_name,
                COALESCE(l.total, 0) AS net_amount,
                COALESCE(l.vat_amount, 0) AS vat_amount,
                (COALESCE(l.total,0) + COALESCE(l.vat_amount,0) - COALESCE(l.withholding_amount,0)) AS grand_total
            FROM purchase_invoices p
            JOIN purchase_invoice_lines l ON l.invoice_id = p.id
            LEFT JOIN products pr ON pr.id = l.product_id
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            WHERE {purchases_where_sql} AND COALESCE(l.vat_amount,0) > 0

            UNION ALL

            SELECT
                p.date,
                'مشتريات' AS doc_type,
                COALESCE(p.doc_no, p.supplier_invoice_no, 'PI-' || printf('%06d', p.id)) AS doc_no,
                COALESCE(s.name, 'مورد نقدي') AS party_name,
                COALESCE(pr.name, '') AS item_name,
                COALESCE(p.total, 0) AS net_amount,
                COALESCE(p.tax_amount, 0) AS vat_amount,
                (COALESCE(p.total,0) + COALESCE(p.tax_amount,0) - COALESCE(p.withholding_amount,0)) AS grand_total
            FROM purchase_invoices p
            LEFT JOIN products pr ON pr.id = p.product_id
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            WHERE {purchases_where_sql}
              AND NOT EXISTS (SELECT 1 FROM purchase_invoice_lines l2 WHERE l2.invoice_id=p.id)
              AND COALESCE(p.tax_amount,0) > 0
        """, params_purchases + params_purchases)

        purchase_rows = cur.fetchall()
        conn.close()

        def clean_doc_no(value):
            value = str(value or "")
            value = value.replace("\ufffe", "-").replace("￾", "-")
            value = value.replace("SI000", "SI-000").replace("PI000", "PI-000")
            return value

        rows = []
        for r in list(sales_rows) + list(purchase_rows):
            rows.append((
                r[0],
                r[1],
                clean_doc_no(r[2]),
                r[3],
                r[4],
                float(r[5] or 0),
                float(r[6] or 0),
                float(r[7] or 0),
            ))

        rows.sort(key=lambda r: (r[0] or "", r[1] or "", r[2] or ""))

        output_vat = sum(r[6] for r in rows if r[1] == "مبيعات")
        input_vat = sum(r[6] for r in rows if r[1] == "مشتريات")
        net_due = output_vat - input_vat

        total_net = sum(r[5] for r in rows)
        total_vat = sum(r[6] for r in rows)
        total_grand = sum(r[7] for r in rows)

        template = """
        {% extends "layout.html" %}
        {% block content %}

        <div class="vat-report-page" dir="rtl">

            <div class="report-header">
                <div>
                    <h2>تقرير ضريبة القيمة المضافة</h2>
                    <p>مخرجات المبيعات ومدخلات المشتريات للفواتير المرحلة فقط</p>
                    {% if date_from or date_to %}
                    <small>
                        الفترة:
                        {% if date_from %} من {{ date_from }} {% endif %}
                        {% if date_to %} إلى {{ date_to }} {% endif %}
                    </small>
                    {% endif %}
                </div>

                <div class="report-actions d-print-none">
                    <button onclick="window.print()" class="btn-print">طباعة / PDF</button>
                </div>
            </div>

            <form method="get" class="filter-box d-print-none">
                <div>
                    <label>من تاريخ</label>
                    <input type="date" name="date_from" value="{{ date_from }}">
                </div>
                <div>
                    <label>إلى تاريخ</label>
                    <input type="date" name="date_to" value="{{ date_to }}">
                </div>
                <div class="filter-actions">
                    <button type="submit">تطبيق الفلتر</button>
                    <a href="{{ url_for('vat_report') }}">إلغاء الفلتر</a>
                </div>
            </form>

            <div class="summary-grid">
                <div class="summary-card output">
                    <span>ضريبة المخرجات</span>
                    <strong>{{ "%.2f"|format(output_vat) }}</strong>
                    <small>ضريبة فواتير البيع</small>
                </div>

                <div class="summary-card input">
                    <span>ضريبة المدخلات</span>
                    <strong>{{ "%.2f"|format(input_vat) }}</strong>
                    <small>ضريبة فواتير الشراء</small>
                </div>

                <div class="summary-card due">
                    <span>الصافي المستحق</span>
                    <strong>{{ "%.2f"|format(net_due) }}</strong>
                    <small>موجب = مستحق، سالب = رصيد مدخلات</small>
                </div>
            </div>

            <div class="report-table-card">
                <div class="table-title">تفاصيل الفواتير الضريبية</div>

                <div class="table-responsive">
                    <table class="vat-table">
                        <thead>
                            <tr>
                                <th>التاريخ</th>
                                <th>النوع</th>
                                <th>رقم المستند</th>
                                <th>العميل / المورد</th>
                                <th>الصنف</th>
                                <th>الصافي قبل الضريبة</th>
                                <th>الضريبة</th>
                                <th>الإجمالي بعد الضريبة</th>
                            </tr>
                        </thead>

                        <tbody>
                            {% for r in rows %}
                            <tr>
                                <td class="nowrap date-cell">{{ r[0] }}</td>
                                <td class="nowrap">
                                    {% if r[1] == "مبيعات" %}
                                        <span class="badge badge-sale">مبيعات</span>
                                    {% else %}
                                        <span class="badge badge-purchase">مشتريات</span>
                                    {% endif %}
                                </td>
                                <td class="nowrap doc-no" dir="ltr">{{ r[2] }}</td>
                                <td class="party-cell">{{ r[3] }}</td>
                                <td class="item-cell">{{ r[4] }}</td>
                                <td class="num">{{ "%.2f"|format(r[5]) }}</td>
                                <td class="num">{{ "%.2f"|format(r[6]) }}</td>
                                <td class="num">{{ "%.2f"|format(r[7]) }}</td>
                            </tr>
                            {% else %}
                            <tr>
                                <td colspan="8" class="empty-row">لا توجد فواتير ضريبية مرحلة.</td>
                            </tr>
                            {% endfor %}
                        </tbody>

                        <tfoot>
                            <tr>
                                <td colspan="5">الإجمالي</td>
                                <td class="num">{{ "%.2f"|format(total_net) }}</td>
                                <td class="num">{{ "%.2f"|format(total_vat) }}</td>
                                <td class="num">{{ "%.2f"|format(total_grand) }}</td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            </div>

        </div>

        <style>
            .vat-report-page {
                background: #f6f8fb;
                padding: 24px;
                font-family: Tahoma, Arial, sans-serif;
                color: #1f2937;
            }

            .report-header {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                gap: 16px;
                margin-bottom: 18px;
            }

            .report-header h2 {
                margin: 0;
                font-size: 28px;
                font-weight: 800;
                color: #111827;
            }

            .report-header p {
                margin: 6px 0 0;
                color: #6b7280;
            }

            .report-header small {
                display: block;
                margin-top: 6px;
                color: #374151;
                font-weight: 600;
            }

            .btn-print {
                border: 0;
                background: #2563eb;
                color: #fff;
                padding: 10px 18px;
                border-radius: 10px;
                font-weight: 700;
                cursor: pointer;
            }

            .filter-box {
                background: #fff;
                border: 1px solid #e5e7eb;
                border-radius: 16px;
                padding: 16px;
                margin-bottom: 18px;
                display: flex;
                align-items: end;
                gap: 14px;
                flex-wrap: wrap;
                box-shadow: 0 8px 20px rgba(15, 23, 42, 0.04);
            }

            .filter-box label {
                display: block;
                font-size: 13px;
                color: #6b7280;
                margin-bottom: 6px;
                font-weight: 700;
            }

            .filter-box input {
                border: 1px solid #d1d5db;
                border-radius: 10px;
                padding: 9px 12px;
                min-width: 180px;
            }

            .filter-actions {
                display: flex;
                gap: 10px;
                align-items: center;
            }

            .filter-actions button {
                background: #111827;
                color: #fff;
                border: 0;
                border-radius: 10px;
                padding: 10px 16px;
                font-weight: 700;
            }

            .filter-actions a {
                color: #6b7280;
                text-decoration: none;
                font-weight: 700;
            }

            .summary-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 16px;
                margin-bottom: 20px;
            }

            .summary-card {
                background: #fff;
                border-radius: 18px;
                padding: 20px;
                border: 1px solid #e5e7eb;
                box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
            }

            .summary-card span {
                display: block;
                color: #6b7280;
                font-size: 14px;
                margin-bottom: 8px;
                font-weight: 700;
            }

            .summary-card strong {
                display: block;
                font-size: 30px;
                line-height: 1.2;
                margin-bottom: 8px;
                direction: ltr;
                text-align: right;
            }

            .summary-card small {
                color: #6b7280;
                font-weight: 600;
            }

            .summary-card.output strong { color: #dc2626; }
            .summary-card.input strong { color: #059669; }
            .summary-card.due strong { color: #2563eb; }

            .report-table-card {
                background: #fff;
                border: 1px solid #e5e7eb;
                border-radius: 18px;
                overflow: hidden;
                box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
            }

            .table-title {
                padding: 16px 18px;
                font-size: 18px;
                font-weight: 800;
                border-bottom: 1px solid #e5e7eb;
                background: #fff;
            }

            .table-responsive {
                width: 100%;
                overflow-x: auto;
            }

            .vat-table {
                width: 100%;
                border-collapse: collapse;
                table-layout: fixed;
                background: #fff;
            }

            .vat-table th {
                background: #111827;
                color: #fff;
                padding: 12px 10px;
                font-size: 13px;
                font-weight: 800;
                border: 1px solid #1f2937;
                text-align: center;
                vertical-align: middle;
            }

            .vat-table td {
                padding: 11px 10px;
                border: 1px solid #e5e7eb;
                font-size: 13px;
                vertical-align: middle;
                background: #fff;
            }

            .vat-table tbody tr:nth-child(even) td {
                background: #f9fafb;
            }

            .vat-table tfoot td {
                background: #f3f4f6;
                font-weight: 900;
                border-top: 2px solid #9ca3af;
            }

            .nowrap {
                white-space: nowrap;
            }

            .date-cell {
                width: 95px;
                direction: ltr;
                text-align: center;
            }

            .doc-no {
                width: 100px;
                text-align: center;
                font-weight: 800;
            }

            .party-cell {
                width: 160px;
                font-weight: 700;
            }

            .item-cell {
                width: 180px;
            }

            .num {
                direction: ltr;
                text-align: left;
                white-space: nowrap;
                font-weight: 700;
                font-variant-numeric: tabular-nums;
            }

            .badge {
                display: inline-block;
                padding: 5px 9px;
                border-radius: 999px;
                font-size: 12px;
                font-weight: 800;
                white-space: nowrap;
            }

            .badge-sale {
                background: #fee2e2;
                color: #991b1b;
            }

            .badge-purchase {
                background: #dcfce7;
                color: #166534;
            }

            .empty-row {
                text-align: center;
                color: #6b7280;
                padding: 28px !important;
            }

            @media (max-width: 768px) {
                .vat-report-page {
                    padding: 14px;
                }

                .summary-grid {
                    grid-template-columns: 1fr;
                }

                .report-header {
                    display: block;
                }

                .report-actions {
                    margin-top: 12px;
                }
            }

            @media print {
                @page {
                    size: A4 landscape;
                    margin: 10mm;
                }

                .sidebar,
                .navbar,
                .d-print-none,
                .btn,
                .report-actions,
                .filter-box {
                    display: none !important;
                }

                html, body {
                    background: #fff !important;
                    -webkit-print-color-adjust: exact;
                    print-color-adjust: exact;
                }

                .vat-report-page {
                    padding: 0 !important;
                    background: #fff !important;
                }

                .report-header {
                    margin-bottom: 12px;
                }

                .report-header h2 {
                    font-size: 22px;
                }

                .summary-grid {
                    grid-template-columns: repeat(3, 1fr);
                    gap: 8px;
                    margin-bottom: 12px;
                }

                .summary-card {
                    box-shadow: none !important;
                    border: 1px solid #ddd !important;
                    border-radius: 10px;
                    padding: 12px;
                }

                .summary-card strong {
                    font-size: 22px;
                }

                .report-table-card {
                    box-shadow: none !important;
                    border-radius: 0;
                }

                .table-title {
                    padding: 10px;
                }

                .vat-table {
                    table-layout: fixed;
                }

                .vat-table th,
                .vat-table td {
                    font-size: 11px;
                    padding: 7px 6px;
                    line-height: 1.35;
                }

                .date-cell,
                .doc-no,
                .num {
                    white-space: nowrap !important;
                }
            }
        </style>

        {% endblock %}
        """

        return render_template_string(
            template,
            rows=rows,
            output_vat=output_vat,
            input_vat=input_vat,
            net_due=net_due,
            total_net=total_net,
            total_vat=total_vat,
            total_grand=total_grand,
            date_from=date_from,
            date_to=date_to,
        )

    return vat_report

def build_withholding_tax_report_view(deps):
    db = deps["db"]

    def withholding_tax_report():
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT s.date,s.doc_no,COALESCE(c.name,'عميل نقدي'),p.name,COALESCE(p.unit,''),l.total,COALESCE(l.withholding_rate,1),COALESCE(l.withholding_amount,0),'بيع',(l.total + COALESCE(l.vat_amount,0) - COALESCE(l.withholding_amount,0))
            FROM sales_invoices s
            JOIN sales_invoice_lines l ON l.invoice_id=s.id
            JOIN products p ON p.id=l.product_id
            LEFT JOIN customers c ON c.id=s.customer_id
            WHERE s.status='posted' AND COALESCE(l.withholding_enabled,0)=1 AND COALESCE(l.withholding_amount,0) > 0
            UNION ALL
            SELECT s.date,s.doc_no,COALESCE(c.name,'عميل نقدي'),p.name,COALESCE(p.unit,''),s.total,COALESCE(s.withholding_rate,1),COALESCE(s.withholding_amount,0),'بيع',(s.total + COALESCE(s.tax_amount,0) - COALESCE(s.withholding_amount,0))
            FROM sales_invoices s
            JOIN products p ON p.id=s.product_id
            LEFT JOIN customers c ON c.id=s.customer_id
            WHERE s.status='posted' AND COALESCE(s.withholding_amount,0) > 0
              AND NOT EXISTS (SELECT 1 FROM sales_invoice_lines l WHERE l.invoice_id=s.id)
            UNION ALL
            SELECT p.date,p.doc_no,COALESCE(s.name,'مورد نقدي'),pr.name,COALESCE(pr.unit,''),l.total,COALESCE(l.withholding_rate,1),COALESCE(l.withholding_amount,0),'شراء',(l.total + COALESCE(l.vat_amount,0) - COALESCE(l.withholding_amount,0))
            FROM purchase_invoices p
            JOIN purchase_invoice_lines l ON l.invoice_id=p.id
            JOIN products pr ON pr.id=l.product_id
            LEFT JOIN suppliers s ON s.id=p.supplier_id
            WHERE p.status='posted' AND COALESCE(l.withholding_enabled,0)=1 AND COALESCE(l.withholding_amount,0) > 0
            UNION ALL
            SELECT p.date,p.doc_no,COALESCE(s.name,'مورد نقدي'),pr.name,COALESCE(pr.unit,''),p.total,COALESCE(p.withholding_rate,1),COALESCE(p.withholding_amount,0),'شراء',p.grand_total
            FROM purchase_invoices p
            JOIN products pr ON pr.id=p.product_id
            LEFT JOIN suppliers s ON s.id=p.supplier_id
            WHERE p.status='posted' AND COALESCE(p.withholding_amount,0) > 0
              AND NOT EXISTS (SELECT 1 FROM purchase_invoice_lines l WHERE l.invoice_id=p.id)
            ORDER BY 1 DESC
            """
        )
        rows = cur.fetchall()
        total_withholding = sum((row[7] or 0) for row in rows)
        conn.close()
        if request.args.get("format") == "excel":
            return _tax_report_excel("withholding-tax-report.xlsx", "تقرير ضريبة الخصم والإضافة", rows, "إجمالي التقرير", total_withholding)
        return render_template("withholding_tax_report.html", rows=rows, total_withholding=total_withholding)

    return withholding_tax_report
