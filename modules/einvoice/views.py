from flask import flash, redirect, render_template, url_for


def build_einvoices_view(deps):
    db = deps["db"]

    def e_invoices():
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id,document_type,document_id,eta_uuid,status,error_message,created_at
            FROM e_invoice_documents
            ORDER BY id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("e_invoices.html", rows=rows)

    return e_invoices


def build_prepare_sales_einvoices_view(deps):
    db = deps["db"]
    log_action = deps["log_action"]

    def prepare_sales_e_invoices():
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT s.id
            FROM sales_invoices s
            LEFT JOIN e_invoice_documents e
                ON e.document_type='sale'
                AND e.document_id=s.id
            WHERE e.id IS NULL
              AND s.status='posted'
            """
        )
        invoice_ids = [row[0] for row in cur.fetchall()]

        for invoice_id in invoice_ids:
            cur.execute(
                """
                INSERT INTO e_invoice_documents(document_type,document_id,status)
                VALUES ('sale',?,'draft')
                """,
                (invoice_id,),
            )

        log_action(cur, "prepare", "e_invoice_documents", None, f"sales_count={len(invoice_ids)}")
        conn.commit()
        conn.close()

        flash(f"تم تجهيز {len(invoice_ids)} فاتورة بيع كمسودات للفاتورة الإلكترونية.", "success")
        return redirect(url_for("e_invoices"))

    return prepare_sales_e_invoices
