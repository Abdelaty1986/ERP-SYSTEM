from io import BytesIO

from flask import flash, redirect, request, send_file, url_for
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font


def _customer_tax_number_expr(customer_columns):
    expressions = []
    for column_name in ("tax_registration_number", "tax_number", "tax_id"):
        if column_name in customer_columns:
            expressions.append(f"NULLIF(c.{column_name}, '')")
    if expressions:
        return f"COALESCE({', '.join(expressions)}, 'غير مسجل')"
    return "'غير مسجل'"


def _sales_invoice_export_query(created_by_expr, join_users_sql, customer_tax_expr, where_sql):
    return f"""
        WITH ordered_lines AS (
            SELECT
                sil.invoice_id,
                p.name AS item_name,
                COALESCE(NULLIF(sil.selected_unit, ''), NULLIF(sil.unit_name, ''), p.unit, 'وحدة') AS selected_unit_name
            FROM sales_invoice_lines sil
            JOIN products p ON p.id = sil.product_id
            ORDER BY sil.invoice_id, sil.id
        ),
        line_summary AS (
            SELECT
                invoice_id,
                GROUP_CONCAT(item_name, ' | ') AS items,
                GROUP_CONCAT(selected_unit_name, ' | ') AS units
            FROM ordered_lines
            GROUP BY invoice_id
        )
        SELECT
            si.id,
            COALESCE(NULLIF(si.invoice_number, ''), si.doc_no) AS invoice_number,
            si.date,
            COALESCE(c.name, 'عميل نقدي') AS customer_name,
            {customer_tax_expr} AS customer_tax_number,
            COALESCE(ls.items, '') AS items,
            COALESCE(ls.units, '') AS units,
            COALESCE(si.payment_type, '') AS payment_type,
            COALESCE(si.total, 0) AS subtotal,
            COALESCE(si.withholding_amount, 0) AS discount_amount,
            COALESCE(si.tax_amount, 0) AS tax_amount,
            COALESCE(si.grand_total, 0) AS net_amount,
            COALESCE(si.status, 'draft') AS status,
            {created_by_expr} AS created_by_name
        FROM sales_invoices si
        LEFT JOIN customers c ON si.customer_id = c.id
        LEFT JOIN line_summary ls ON ls.invoice_id = si.id
        {join_users_sql}
        {where_sql}
        ORDER BY si.id DESC
    """


def _sales_invoice_export_rows(cur, from_date=None, to_date=None):
    sales_invoice_columns = {row[1] for row in cur.execute("PRAGMA table_info(sales_invoices)").fetchall()}
    customer_columns = {row[1] for row in cur.execute("PRAGMA table_info(customers)").fetchall()}
    user_columns = {row[1] for row in cur.execute("PRAGMA table_info(users)").fetchall()} if cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'").fetchone() else set()

    created_by_expr = "''"
    join_users_sql = ""
    if "created_by" in sales_invoice_columns:
        if "username" in user_columns:
            join_users_sql = "LEFT JOIN users u ON CAST(u.id AS TEXT)=CAST(si.created_by AS TEXT) OR u.username=si.created_by"
            created_by_expr = "COALESCE(u.username, si.created_by, '')"
        else:
            created_by_expr = "COALESCE(si.created_by, '')"

    params = []
    where_sql = ""
    if from_date and to_date:
        where_sql = "WHERE si.date >= ? AND si.date <= ?"
        params.extend([from_date, to_date])

    query = _sales_invoice_export_query(
        created_by_expr=created_by_expr,
        join_users_sql=join_users_sql,
        customer_tax_expr=_customer_tax_number_expr(customer_columns),
        where_sql=where_sql,
    )
    cur.execute(query, params)
    return cur.fetchall()


def build_export_sales_invoices_excel_view(deps):
    db = deps["db"]

    def export_sales_invoices_excel():
        from_date = (request.args.get("from_date") or "").strip()
        to_date = (request.args.get("to_date") or "").strip()
        if not from_date or not to_date:
            flash("اختر من تاريخ وإلى تاريخ قبل تحميل ملف Excel.", "warning")
            return redirect(url_for("sales_invoices"))

        conn = db()
        cur = conn.cursor()
        rows = _sales_invoice_export_rows(cur, from_date, to_date)
        conn.close()

        wb = Workbook()
        ws = wb.active
        ws.title = "Sales Invoices"
        ws.sheet_view.rightToLeft = True
        headers = [
            "رقم الفاتورة",
            "تاريخ الفاتورة",
            "اسم العميل",
            "رقم التسجيل الضريبي",
            "الأصناف",
            "الوحدة",
            "نوع الدفع",
            "الإجمالي قبل الخصم",
            "الخصم",
            "الضريبة",
            "الصافي",
            "حالة الترحيل",
            "اسم المستخدم",
        ]
        ws.append(headers)
        for idx, _title in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=idx)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")

        payment_labels = {"cash": "نقدي", "credit": "آجل"}
        status_labels = {"draft": "غير مرحلة", "posted": "مرحلة", "cancelled": "ملغاة"}
        for row in rows:
            ws.append(
                [
                    row[1] or f"SAL-{row[0]}",
                    row[2] or "",
                    row[3] or "عميل نقدي",
                    row[4] or "غير مسجل",
                    row[5] or "",
                    row[6] or "",
                    payment_labels.get(row[7], row[7] or ""),
                    float(row[8] or 0),
                    float(row[9] or 0),
                    float(row[10] or 0),
                    float(row[11] or 0),
                    status_labels.get(row[12], row[12] or ""),
                    row[13] or "",
                ]
            )

        for column, width in zip("ABCDEFGHIJKLM", [18, 16, 28, 22, 34, 24, 14, 18, 14, 14, 16, 16, 20]):
            ws.column_dimensions[column].width = width

        out = BytesIO()
        wb.save(out)
        out.seek(0)
        return send_file(
            out,
            as_attachment=True,
            download_name=f"sales_invoices_{from_date}_to_{to_date}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    return export_sales_invoices_excel


def build_tax_portal_sales_excel_view(deps):
    db = deps["db"]
    excel_response = deps["excel_response"]

    def export_all_sales_excel():
        conn = db()
        cur = conn.cursor()
        rows = _sales_invoice_export_rows(cur)
        conn.close()
        formatted_rows = [
            (
                row[0],
                row[1] or f"SAL-{row[0]}",
                row[2],
                row[3],
                row[4],
                row[5],
                row[6],
                row[7],
                row[8],
                row[9],
                row[10],
                row[11],
                row[12],
                row[13],
            )
            for row in rows
        ]
        headers = [
            "id",
            "doc_no",
            "date",
            "customer_name",
            "customer_tax_number",
            "items",
            "units",
            "payment_type",
            "total_amount",
            "discount_amount",
            "tax_amount",
            "grand_total",
            "status",
            "created_by_name",
        ]
        return excel_response(
            "sales_invoices_all.xls",
            headers,
            formatted_rows,
            title="تقرير فواتير المبيعات",
        )

    return export_all_sales_excel
