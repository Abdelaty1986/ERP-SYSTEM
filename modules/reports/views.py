from flask import render_template, request


def _invoice_net(expression):
    return f"({expression} - COALESCE(withholding_amount,0))"


def build_customers_report_view(deps):
    db = deps["db"]
    excel_response = deps["excel_response"]

    def customers_report():
        conn = db()
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT c.id,c.name,
                   COALESCE(SUM(CASE WHEN s.payment_type='credit' AND s.status='posted' THEN {_invoice_net('s.grand_total')} ELSE 0 END),0)
                   + COALESCE((SELECT SUM({ _invoice_net('f.grand_total') }) FROM financial_sales_invoices f WHERE f.customer_id=c.id AND f.status='posted' AND f.payment_type='credit'),0)
                   + COALESCE((SELECT SUM(CASE WHEN a.adjustment_type='debit' THEN a.grand_total ELSE 0 END) FROM customer_adjustments a WHERE a.customer_id=c.id AND a.status='posted'),0)
                   AS invoices,
                   COALESCE((SELECT SUM(r.amount) FROM receipt_vouchers r WHERE r.customer_id=c.id AND r.status='posted'),0)
                   + COALESCE((SELECT SUM(CASE WHEN a.adjustment_type='credit' THEN a.grand_total ELSE 0 END) FROM customer_adjustments a WHERE a.customer_id=c.id AND a.status='posted'),0)
                   AS receipts,
                   COALESCE((SELECT SUM(s2.withholding_amount) FROM sales_invoices s2 WHERE s2.customer_id=c.id AND s2.status='posted'),0)
                   + COALESCE((SELECT SUM(f2.withholding_amount) FROM financial_sales_invoices f2 WHERE f2.customer_id=c.id AND f2.status='posted'),0)
                   AS withholding_amount
            FROM customers c
            LEFT JOIN sales_invoices s ON c.id=s.customer_id
            GROUP BY c.id
            ORDER BY c.name
            """
        )
        rows = []
        for customer_id, name, invoices, receipts, withholding_amount in cur.fetchall():
            rows.append((customer_id, name, invoices, receipts, invoices - receipts, withholding_amount))
        total_balance = sum(row[4] for row in rows)
        if request.args.get("format") == "excel":
            conn.close()
            return excel_response(
                "customers-report.xls",
                ["العميل", "فواتير آجلة", "تحصيلات", "الرصيد", "خصم وإضافة مدينة"],
                [(row[1], row[2], row[3], row[4], row[5]) for row in rows],
                title="تقرير العملاء",
            )
        conn.close()
        return render_template("customers_report.html", rows=rows, total_balance=total_balance)

    return customers_report


def build_suppliers_report_view(deps):
    db = deps["db"]
    excel_response = deps["excel_response"]

    def suppliers_report():
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT s.id,s.name,
                   COALESCE(SUM(CASE WHEN p.payment_type='credit' AND p.status='posted' THEN p.grand_total - COALESCE(p.withholding_amount,0) ELSE 0 END),0) AS invoices,
                   COALESCE((SELECT SUM(v.amount) FROM payment_vouchers v WHERE v.supplier_id=s.id AND v.status='posted'),0) AS payments,
                   COALESCE((SELECT SUM(p2.withholding_amount) FROM purchase_invoices p2 WHERE p2.supplier_id=s.id AND p2.status='posted'),0) AS withholding_amount
            FROM suppliers s
            LEFT JOIN purchase_invoices p ON s.id=p.supplier_id
            GROUP BY s.id
            ORDER BY s.name
            """
        )
        rows = []
        for supplier_id, name, invoices, payments, withholding_amount in cur.fetchall():
            rows.append((supplier_id, name, invoices, payments, invoices - payments, withholding_amount))
        total_balance = sum(row[4] for row in rows)
        if request.args.get("format") == "excel":
            conn.close()
            return excel_response(
                "suppliers-report.xls",
                ["المورد", "فواتير آجلة", "مدفوعات", "الرصيد", "خصم وإضافة دائنة"],
                [(row[1], row[2], row[3], row[4], row[5]) for row in rows],
                title="تقرير الموردين",
            )
        conn.close()
        return render_template("suppliers_report.html", rows=rows, total_balance=total_balance)

    return suppliers_report


def build_customers_aging_report_view(deps):
    db = deps["db"]
    build_aging_rows = deps["build_aging_rows"]
    excel_response = deps["excel_response"]

    def customers_aging_report():
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT c.id,c.name,s.date,s.due_date,(s.grand_total - COALESCE(s.withholding_amount,0))
            FROM sales_invoices s
            JOIN customers c ON c.id=s.customer_id
            WHERE s.status='posted' AND s.payment_type='credit'
            UNION ALL
            SELECT c.id,c.name,f.date,f.due_date,(f.grand_total - COALESCE(f.withholding_amount,0))
            FROM financial_sales_invoices f
            JOIN customers c ON c.id=f.customer_id
            WHERE f.status='posted' AND f.payment_type='credit'
            UNION ALL
            SELECT c.id,c.name,a.date,a.date,a.grand_total
            FROM customer_adjustments a
            JOIN customers c ON c.id=a.customer_id
            WHERE a.status='posted' AND a.adjustment_type='debit'
            ORDER BY 2,4,3
            """
        )
        invoice_rows = cur.fetchall()
        cur.execute(
            """
            SELECT customer_id,COALESCE(SUM(amount),0)
            FROM receipt_vouchers
            WHERE status='posted'
            GROUP BY customer_id
            """
        )
        settlement_map = {}
        for customer_id, amount in cur.fetchall():
            settlement_map[customer_id] = settlement_map.get(customer_id, 0) + (amount or 0)
        cur.execute(
            """
            SELECT customer_id,COALESCE(SUM(grand_total),0)
            FROM customer_adjustments
            WHERE status='posted' AND adjustment_type='credit'
            GROUP BY customer_id
            """
        )
        for customer_id, amount in cur.fetchall():
            settlement_map[customer_id] = settlement_map.get(customer_id, 0) + (amount or 0)
        conn.close()
        rows, totals = build_aging_rows(invoice_rows, list(settlement_map.items()))
        if request.args.get("format") == "excel":
            return excel_response(
                "customers-aging.xls",
                ["العميل", "رصيد حالي", "1-30", "31-60", "61-90", "أكثر من 90", "الإجمالي"],
                [(row[1], row[2], row[3], row[4], row[5], row[6], sum(row[2:7])) for row in rows],
                title="أعمار ديون العملاء",
            )
        return render_template(
            "aging_report.html",
            title="أعمار ديون العملاء",
            party_label="العميل",
            statement_endpoint="customer_statement",
            rows=rows,
            totals=totals,
        )

    return customers_aging_report


def build_suppliers_aging_report_view(deps):
    db = deps["db"]
    build_aging_rows = deps["build_aging_rows"]
    excel_response = deps["excel_response"]

    def suppliers_aging_report():
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT s.id,s.name,p.date,p.due_date,(p.grand_total - COALESCE(p.withholding_amount,0))
            FROM purchase_invoices p
            JOIN suppliers s ON s.id=p.supplier_id
            WHERE p.status='posted' AND p.payment_type='credit'
            ORDER BY s.name,p.due_date,p.date
            """
        )
        invoice_rows = cur.fetchall()
        cur.execute(
            """
            SELECT supplier_id,COALESCE(SUM(amount),0)
            FROM payment_vouchers
            WHERE status='posted'
            GROUP BY supplier_id
            """
        )
        settlement_rows = cur.fetchall()
        conn.close()
        rows, totals = build_aging_rows(invoice_rows, settlement_rows)
        if request.args.get("format") == "excel":
            return excel_response(
                "suppliers-aging.xls",
                ["المورد", "رصيد حالي", "1-30", "31-60", "61-90", "أكثر من 90", "الإجمالي"],
                [(row[1], row[2], row[3], row[4], row[5], row[6], sum(row[2:7])) for row in rows],
                title="أعمار مديونيات الموردين",
            )
        return render_template(
            "aging_report.html",
            title="أعمار مديونيات الموردين",
            party_label="المورد",
            statement_endpoint="supplier_statement",
            rows=rows,
            totals=totals,
        )

    return suppliers_aging_report
