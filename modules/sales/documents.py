from flask import flash, redirect, render_template, url_for


def build_print_sale_view(deps):
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
                   p.name,p.unit,s.quantity,s.unit_price,s.total,s.tax_rate,s.tax_amount,s.withholding_rate,s.withholding_amount,s.grand_total,
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
            amount_in_words=amount_to_words(doc[14]),
        )

    return print_sale


def build_print_purchase_view(deps):
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
                   pr.name,pr.unit,p.quantity,p.unit_price,p.total,p.tax_rate,p.tax_amount,p.withholding_rate,p.withholding_amount,p.grand_total,
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
            flash("فاتورة المورد غير موجودة.", "danger")
            return redirect(url_for("purchases"))
        return render_template(
            "print_document.html",
            company=company,
            doc=doc,
            doc_type="تسجيل فاتورة مورد",
            party_label="المورد",
            supplier_invoice=True,
            amount_in_words=amount_to_words(doc[14]),
        )

    return print_purchase


def build_print_sales_credit_note_view(deps):
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
            flash("إشعار التسوية الدائن غير موجود.", "danger")
            return redirect(url_for("sales_credit_notes"))
        return render_template(
            "print_customer_note.html",
            company=company,
            doc=doc,
            doc_title="إشعار تسوية دائن للعميل",
            note_kind="credit",
            party_label="العميل",
            amount_in_words=amount_to_words(doc[12]),
            source_label=f"من واقع مردودات المبيعات رقم {doc[14]} / الفاتورة الأصلية رقم {doc[15]}",
        )

    return print_sales_credit_note


def build_print_supplier_debit_note_view(deps):
    db = deps["db"]
    get_company_settings = deps["get_company_settings"]
    amount_to_words = deps["amount_to_words"]

    def print_supplier_debit_note(id):
        conn = db()
        cur = conn.cursor()
        company = get_company_settings(cur)
        cur.execute(
            """
            SELECT sdn.id,sdn.date,sdn.doc_no,COALESCE(s.name,'مورد نقدي'),COALESCE(s.phone,''),COALESCE(s.address,''),
                   p.name,p.unit,sdn.quantity,sdn.unit_price,sdn.total,sdn.tax_amount,sdn.grand_total,
                   sdn.notes,sdn.purchase_return_id,sdn.purchase_invoice_id
            FROM supplier_debit_notes sdn
            LEFT JOIN suppliers s ON s.id=sdn.supplier_id
            LEFT JOIN products p ON p.id=sdn.product_id
            WHERE sdn.id=?
            """,
            (id,),
        )
        doc = cur.fetchone()
        conn.close()
        if not doc:
            flash("إشعار التسوية المدين غير موجود.", "danger")
            return redirect(url_for("supplier_debit_notes"))
        return render_template(
            "print_customer_note.html",
            company=company,
            doc=doc,
            doc_title="إشعار تسوية مدين للمورد",
            note_kind="debit",
            party_label="المورد",
            amount_in_words=amount_to_words(doc[12]),
            source_label=f"من واقع مردودات المشتريات رقم {doc[14]} / الفاتورة الأصلية رقم {doc[15]}",
        )

    return print_supplier_debit_note


def build_prepare_sales_credit_note_einvoice_view(deps):
    db = deps["db"]
    prepare_einvoice_document = deps["prepare_einvoice_document"]
    log_action = deps["log_action"]

    def prepare_sales_credit_note_einvoice(id):
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM sales_credit_notes WHERE id=?", (id,))
        if not cur.fetchone():
            conn.close()
            flash("إشعار التسوية الدائن غير موجود.", "danger")
            return redirect(url_for("sales_credit_notes"))
        _, created = prepare_einvoice_document(cur, "sales_credit_note", id)
        log_action(cur, "prepare", "e_invoice_documents", None, f"sales_credit_note={id}")
        conn.commit()
        conn.close()
        flash("تم تجهيز إشعار التسوية الدائن للرفع على بوابة الضرائب." if created else "إشعار التسوية الدائن مجهز بالفعل للرفع.", "success")
        return redirect(url_for("sales_credit_notes"))

    return prepare_sales_credit_note_einvoice
