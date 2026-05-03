from flask import flash, redirect, render_template, request, url_for

from modules.sales.taxing import invoice_totals, parse_flag, taxable_line


def _customer_withholding(cur, customer_id):
    if not customer_id:
        return 0
    cur.execute("SELECT withholding_status FROM customers WHERE id=?", (customer_id,))
    row = cur.fetchone()
    return 1 if row and row[0] == "subject" else 0


def _supplier_withholding(cur, supplier_id):
    if not supplier_id:
        return 0
    cur.execute("SELECT withholding_status FROM suppliers WHERE id=?", (supplier_id,))
    row = cur.fetchone()
    return 1 if row and row[0] == "taxable" else 0


def build_sales_invoice_from_delivery_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    next_document_number = deps["next_document_number"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]

    def sales_invoice_from_delivery():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            delivery_ids = [int(parse_positive_amount(item) or 0) for item in request.form.getlist("delivery_ids")]
            date_value = request.form.get("date", "").strip()
            due_date = request.form.get("due_date", "").strip()
            payment_type = request.form.get("payment_type", "credit")
            po_ref = request.form.get("po_ref", "").strip()
            gr_ref = request.form.get("gr_ref", "").strip()
            notes = request.form.get("notes", "").strip()
            delivery_ids = [item for item in delivery_ids if item > 0]
            deliveries = []
            if delivery_ids:
                placeholders = ",".join(["?"] * len(delivery_ids))
                cur.execute(
                    f"""
                    SELECT sd.id,sd.delivery_no,sd.sales_order_id,sd.customer_id,sd.product_id,sd.delivered_quantity,sd.unit_price,
                           sd.total,sd.cost_total,sd.tax_rate,sd.tax_amount,sd.grand_total,sd.invoice_id,p.name,
                           sd.unit_id,COALESCE(sd.unit_name, p.unit, 'وحدة'),COALESCE(NULLIF(sd.conversion_factor, 0), 1),COALESCE(sd.quantity_base, sd.delivered_quantity)
                    FROM sales_delivery_notes sd
                    JOIN products p ON p.id=sd.product_id
                    WHERE sd.id IN ({placeholders})
                    ORDER BY sd.id
                    """,
                    delivery_ids,
                )
                deliveries = cur.fetchall()
            if not date_value:
                flash("تاريخ الفاتورة مطلوب.", "danger")
            elif not deliveries:
                flash("اختر إذن صرف واحدًا على الأقل.", "danger")
            elif any(row[12] for row in deliveries):
                flash("يوجد إذن صرف تم عمل فاتورة له من قبل.", "danger")
            elif len({row[3] for row in deliveries}) > 1:
                flash("لا يمكن تجميع أذون صرف لأكثر من عميل في نفس الفاتورة.", "danger")
            elif payment_type == "credit" and not deliveries[0][3]:
                flash("الفاتورة الآجلة تحتاج عميلًا مرتبطًا بأمر البيع.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("sales_invoice_from_delivery"))
                doc_no = next_document_number(cur, "sales")
                debit_code = "1300" if payment_type == "credit" else "1100"
                line_rows = []
                for row in deliveries:
                    default_withholding = _customer_withholding(cur, row[3])
                    line = taxable_line(
                        row[5] * row[6],
                        parse_flag(request.form.get(f"vat_enabled_{row[0]}"), (row[9] or 0) > 0),
                        parse_flag(request.form.get(f"withholding_enabled_{row[0]}"), default_withholding > 0),
                        parse_positive_amount(request.form.get(f"vat_rate_{row[0]}", row[9] or 14)),
                        parse_positive_amount(request.form.get(f"withholding_rate_{row[0]}", default_withholding or 1)),
                    )
                    line_rows.append((row, line))
                totals = invoice_totals([line for _, line in line_rows])
                total = totals["total"]
                cost_total = sum(row[8] for row, _ in line_rows)
                tax_amount = totals["tax_amount"]
                grand_total = totals["grand_total"]
                withholding_amount = totals["withholding_amount"]
                first = deliveries[0]
                quantity_total = sum(row[5] for row, _ in line_rows)
                unit_price_value = first[6] if len(line_rows) == 1 else (total / quantity_total if quantity_total else 0)
                delivery_refs = ", ".join(row[1] for row in deliveries)
                withholding_journal_id = create_auto_journal(cur, date_value, f"ضريبة خصم وإضافة عميل على فاتورة بيع {doc_no}", "1510", debit_code, withholding_amount) if withholding_amount > 0 else None
                journal_id = create_auto_journal(cur, date_value, f"فاتورة بيع {doc_no} من أذون صرف {delivery_refs}", debit_code, "4100", total)
                tax_journal_id = create_auto_journal(cur, date_value, f"ضريبة فاتورة بيع {doc_no}", debit_code, "2200", tax_amount) if tax_amount > 0 else None
                cur.execute(
                    """
                    INSERT INTO sales_invoices(
                        date,due_date,doc_no,customer_id,product_id,quantity,unit_price,total,cost_total,
                        tax_rate,tax_amount,withholding_rate,withholding_amount,grand_total,payment_type,journal_id,tax_journal_id,withholding_journal_id,cogs_journal_id,
                        status,sales_order_id,sales_delivery_id,po_ref,gr_ref,notes
                    )
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        date_value,
                        due_date,
                        doc_no,
                        first[3],
                        first[4],
                        quantity_total,
                        unit_price_value,
                        total,
                        cost_total,
                        line_rows[0][1]["vat_rate"] if line_rows else 14,
                        tax_amount,
                        max((line["withholding_rate"] for _, line in line_rows), default=0),
                        withholding_amount,
                        grand_total,
                        payment_type,
                        journal_id,
                        tax_journal_id,
                        withholding_journal_id,
                        None,
                        "posted",
                        first[2],
                        first[0],
                        po_ref,
                        gr_ref or delivery_refs,
                        notes,
                    ),
                )
                invoice_id = cur.lastrowid
                for row, line in line_rows:
                    cur.execute(
                        """
                        INSERT INTO sales_invoice_lines(
                            invoice_id,product_id,quantity,unit_id,unit_name,conversion_factor,quantity_base,unit_price,total,cost_total,
                            vat_enabled,withholding_enabled,vat_rate,withholding_rate,vat_amount,withholding_amount
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            invoice_id,
                            row[4],
                            row[5],
                            row[14],
                            row[15],
                            row[16],
                            row[17],
                            row[6],
                            line["subtotal"],
                            row[8],
                            line["vat_enabled"],
                            line["withholding_enabled"],
                            line["vat_rate"],
                            line["withholding_rate"],
                            line["vat_amount"],
                            line["withholding_amount"],
                        ),
                    )
                    cur.execute("UPDATE sales_delivery_notes SET invoice_id=?, status='invoiced' WHERE id=?", (invoice_id, row[0]))
                mark_journal_source(cur, "sales", invoice_id, journal_id, tax_journal_id, withholding_journal_id)
                log_action(cur, "create", "sales_invoice", invoice_id, f"{doc_no}; DN={delivery_refs}; total={grand_total}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash(f"تم تسجيل فاتورة البيع {doc_no} من أذون الصرف.", "success")
                return redirect(url_for("sales"))

        selected_order_id = int(parse_positive_amount(request.args.get("sales_order_id")) or 0)
        selected_delivery_no = (request.args.get("delivery_no") or "").strip()
        filters = ["COALESCE(sd.invoice_id,0)=0", "sd.status!='invoiced'"]
        params = []
        if selected_order_id:
            filters.append("sd.sales_order_id=?")
            params.append(selected_order_id)
        if selected_delivery_no:
            filters.append("sd.delivery_no=?")
            params.append(selected_delivery_no)
        where_clause = " AND ".join(filters)
        cur.execute(
            f"""
            SELECT sd.id,sd.delivery_no,sd.date,sd.sales_order_id,COALESCE(c.name,'بيع نقدي'),p.name,
                   sd.delivered_quantity,sd.unit_price,sd.total,sd.tax_amount,sd.grand_total
            FROM sales_delivery_notes sd
            LEFT JOIN customers c ON c.id=sd.customer_id
            JOIN products p ON p.id=sd.product_id
            WHERE {where_clause}
            ORDER BY sd.id DESC
            """,
            params,
        )
        open_deliveries = cur.fetchall()
        selected_delivery_ids = {row[0] for row in open_deliveries if selected_delivery_no and row[1] == selected_delivery_no}
        conn.close()
        return render_template(
            "sales_invoice_from_delivery.html",
            open_deliveries=open_deliveries,
            selected_order_id=selected_order_id,
            selected_delivery_no=selected_delivery_no,
            selected_delivery_ids=selected_delivery_ids,
        )

    return sales_invoice_from_delivery


def build_financial_sales_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    next_document_number = deps["next_document_number"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]
    default_tax_rate = deps["DEFAULT_TAX_RATE"]

    def financial_sales():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            due_date = request.form.get("due_date", "").strip()
            customer_id = request.form.get("customer_id") or None
            descriptions = [item.strip() for item in request.form.getlist("description[]")]
            amounts = [parse_positive_amount(item) for item in request.form.getlist("amount[]")]
            if not descriptions:
                descriptions = [request.form.get("description", "").strip()]
                amounts = [parse_positive_amount(request.form.get("amount"))]
            lines = [(desc, amount) for desc, amount in zip(descriptions, amounts) if desc and amount > 0]
            description = "فاتورة بيع مالية متعددة البنود"
            amount = sum(line[1] for line in lines)
            tax_rate = parse_positive_amount(request.form.get("tax_rate", default_tax_rate))
            payment_type = request.form.get("payment_type", "credit")
            revenue_account_id = request.form.get("revenue_account_id") or None
            po_ref = request.form.get("po_ref", "").strip()
            gr_ref = request.form.get("gr_ref", "").strip()
            notes = request.form.get("notes", "").strip()
            cur.execute("SELECT code FROM accounts WHERE id=? AND type='إيرادات'", (revenue_account_id,))
            revenue_account = cur.fetchone()
            if not date_value:
                flash("تاريخ الفاتورة مطلوب.", "danger")
            elif not lines:
                flash("أدخل بندًا واحدًا على الأقل بقيمة صحيحة.", "danger")
            elif amount <= 0:
                flash("قيمة الفاتورة يجب أن تكون أكبر من صفر.", "danger")
            elif payment_type == "credit" and not customer_id:
                flash("الفاتورة الآجلة تحتاج اختيار عميل.", "danger")
            elif not revenue_account:
                flash("اختر حساب إيراد صحيح.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("financial_sales"))
                doc_no = next_document_number(cur, "financial_sales")
                tax_amount = amount * tax_rate / 100
                grand_total = amount + tax_amount
                withholding_rate = _customer_withholding(cur, customer_id)
                withholding_amount = round(grand_total * withholding_rate / 100, 2)
                debit_code = "1300" if payment_type == "credit" else "1100"
                withholding_journal_id = create_auto_journal(cur, date_value, f"ضريبة خصم وإضافة عميل على فاتورة بيع مالية {doc_no}", "1510", debit_code, withholding_amount) if withholding_amount > 0 else None
                journal_id = create_auto_journal(cur, date_value, f"فاتورة بيع مالية {doc_no}", debit_code, revenue_account[0], amount)
                tax_journal_id = create_auto_journal(cur, date_value, f"ضريبة فاتورة بيع مالية {doc_no}", debit_code, "2200", tax_amount) if tax_amount > 0 else None
                cur.execute(
                    """
                    INSERT INTO financial_sales_invoices(
                        date,due_date,doc_no,customer_id,description,amount,tax_rate,tax_amount,withholding_rate,withholding_amount,grand_total,
                        payment_type,revenue_account_id,journal_id,tax_journal_id,withholding_journal_id,status,po_ref,gr_ref,notes
                    )
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (date_value, due_date, doc_no, customer_id, description, amount, tax_rate, tax_amount, withholding_rate, withholding_amount, grand_total, payment_type, revenue_account_id, journal_id, tax_journal_id, withholding_journal_id, "posted", po_ref, gr_ref, notes),
                )
                invoice_id = cur.lastrowid
                for line_desc, line_amount in lines:
                    cur.execute("INSERT INTO financial_sales_invoice_lines(invoice_id,description,amount) VALUES (?,?,?)", (invoice_id, line_desc, line_amount))
                mark_journal_source(cur, "financial_sales", invoice_id, journal_id, tax_journal_id, withholding_journal_id)
                log_action(cur, "create", "financial_sales_invoice", invoice_id, f"{doc_no}; total={grand_total}; withholding={withholding_amount}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash(f"تم تسجيل فاتورة البيع المالية {doc_no}.", "success")
                return redirect(url_for("financial_sales"))

        cur.execute("SELECT id,name FROM customers ORDER BY name")
        customers_rows = cur.fetchall()
        cur.execute("SELECT id,code,name FROM accounts WHERE type='إيرادات' ORDER BY code")
        revenue_accounts = cur.fetchall()
        cur.execute(
            """
            SELECT f.id,f.doc_no,f.date,COALESCE(c.name,'نقدي'),f.description,f.amount,
                   f.tax_amount,f.withholding_amount,f.grand_total,f.payment_type,f.po_ref,f.gr_ref,f.notes
            FROM financial_sales_invoices f
            LEFT JOIN customers c ON c.id=f.customer_id
            ORDER BY f.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("financial_sales.html", customers=customers_rows, revenue_accounts=revenue_accounts, rows=rows)

    return financial_sales


def build_purchase_invoice_from_receipt_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    next_document_number = deps["next_document_number"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]

    def purchase_invoice_from_receipt():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            receipt_ids = [int(parse_positive_amount(item) or 0) for item in request.form.getlist("receipt_ids")]
            date_value = request.form.get("date", "").strip()
            supplier_invoice_no = request.form.get("supplier_invoice_no", "").strip()
            supplier_invoice_date = request.form.get("supplier_invoice_date", "").strip()
            due_date = request.form.get("due_date", "").strip()
            payment_type = request.form.get("payment_type", "credit")
            notes = request.form.get("notes", "").strip()
            receipt_ids = [item for item in receipt_ids if item > 0]
            receipts = []
            if receipt_ids:
                placeholders = ",".join(["?"] * len(receipt_ids))
                cur.execute(
                    f"""
                    SELECT pr.id,pr.receipt_no,pr.date,pr.purchase_order_id,pr.supplier_id,pr.product_id,pr.received_quantity,
                           pr.unit_price,pr.total,pr.tax_rate,pr.tax_amount,pr.grand_total,pr.invoice_id,p.name,
                           pr.unit_id,COALESCE(pr.unit_name, p.unit, 'وحدة'),COALESCE(NULLIF(pr.conversion_factor, 0), 1),COALESCE(pr.quantity_base, pr.received_quantity)
                    FROM purchase_receipts pr
                    JOIN products p ON p.id=pr.product_id
                    WHERE pr.id IN ({placeholders})
                    ORDER BY pr.id
                    """,
                    receipt_ids,
                )
                receipts = cur.fetchall()
            if not date_value or not supplier_invoice_no or not supplier_invoice_date:
                flash("تاريخ التسجيل ورقم وتاريخ فاتورة المورد مطلوبون.", "danger")
            elif not receipts:
                flash("اختر إذن إضافة واحدًا على الأقل.", "danger")
            elif any(row[12] for row in receipts):
                flash("يوجد إذن إضافة تم عمل فاتورة له من قبل.", "danger")
            elif len({row[4] for row in receipts}) > 1:
                flash("لا يمكن تجميع أذون استلام لأكثر من مورد في نفس الفاتورة.", "danger")
            elif payment_type == "credit" and not receipts[0][4]:
                flash("لا يوجد مورد مرتبط بأذون الاستلام المختارة.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("purchase_invoice_from_receipt"))
                doc_no = next_document_number(cur, "purchases")
                credit_code = "2100" if payment_type == "credit" else "1100"
                line_rows = []
                for row in receipts:
                    default_withholding = _supplier_withholding(cur, row[4])
                    line = taxable_line(
                        row[6] * row[7],
                        parse_flag(request.form.get(f"vat_enabled_{row[0]}"), (row[9] or 0) > 0),
                        parse_flag(request.form.get(f"withholding_enabled_{row[0]}"), default_withholding > 0),
                        parse_positive_amount(request.form.get(f"vat_rate_{row[0]}", row[9] or 14)),
                        parse_positive_amount(request.form.get(f"withholding_rate_{row[0]}", default_withholding or 1)),
                    )
                    line_rows.append((row, line))
                totals = invoice_totals([line for _, line in line_rows])
                total = totals["total"]
                tax_amount = totals["tax_amount"]
                grand_total = totals["grand_total"]
                withholding_amount = totals["withholding_amount"]
                first = receipts[0]
                quantity_total = sum(row[6] for row, _ in line_rows)
                unit_price_value = first[7] if len(line_rows) == 1 else (total / quantity_total if quantity_total else 0)
                receipt_refs = ", ".join(row[1] for row in receipts)
                withholding_journal_id = create_auto_journal(cur, date_value, f"ضريبة خصم وإضافة مورد على فاتورة مورد {doc_no}", ("2100" if payment_type == "credit" else "1100"), "2230", withholding_amount) if withholding_amount > 0 else None
                journal_id = create_auto_journal(cur, date_value, f"فاتورة مورد {doc_no} مقابل أذون استلام {receipt_refs}", "2150", credit_code, total)
                tax_journal_id = create_auto_journal(cur, date_value, f"ضريبة فاتورة مورد {doc_no}", "1500", credit_code, tax_amount) if tax_amount > 0 else None
                cur.execute(
                    """
                    INSERT INTO purchase_invoices(
                        date,doc_no,supplier_invoice_no,supplier_invoice_date,due_date,supplier_id,product_id,
                        quantity,unit_price,total,tax_rate,tax_amount,withholding_rate,withholding_amount,grand_total,payment_type,journal_id,
                        tax_journal_id,withholding_journal_id,notes,status,purchase_order_id,purchase_receipt_id
                    )
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        date_value,
                        doc_no,
                        supplier_invoice_no,
                        supplier_invoice_date,
                        due_date,
                        first[4],
                        first[5],
                        quantity_total,
                        unit_price_value,
                        total,
                        line_rows[0][1]["vat_rate"] if line_rows else 14,
                        tax_amount,
                        max((line["withholding_rate"] for _, line in line_rows), default=0),
                        withholding_amount,
                        grand_total,
                        payment_type,
                        journal_id,
                        tax_journal_id,
                        withholding_journal_id,
                        notes,
                        "posted",
                        first[3],
                        first[0],
                    ),
                )
                invoice_id = cur.lastrowid
                for row, line in line_rows:
                    cur.execute(
                        """
                        INSERT INTO purchase_invoice_lines(
                            invoice_id,product_id,quantity,unit_id,unit_name,conversion_factor,quantity_base,unit_price,total,
                            vat_enabled,withholding_enabled,vat_rate,withholding_rate,vat_amount,withholding_amount
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            invoice_id,
                            row[5],
                            row[6],
                            row[14],
                            row[15],
                            row[16],
                            row[17],
                            row[7],
                            line["subtotal"],
                            line["vat_enabled"],
                            line["withholding_enabled"],
                            line["vat_rate"],
                            line["withholding_rate"],
                            line["vat_amount"],
                            line["withholding_amount"],
                        ),
                    )
                    cur.execute("UPDATE purchase_receipts SET invoice_id=?, status='invoiced' WHERE id=?", (invoice_id, row[0]))
                mark_journal_source(cur, "purchases", invoice_id, journal_id, tax_journal_id, withholding_journal_id)
                log_action(cur, "create", "purchase_invoice", invoice_id, f"{doc_no}; GRN={receipt_refs}; total={grand_total}; withholding={withholding_amount}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash(f"تم تسجيل فاتورة المورد {doc_no} من أذون الاستلام المختارة.", "success")
                return redirect(url_for("purchases"))

        cur.execute(
            """
            SELECT pr.id,pr.receipt_no,pr.date,pr.purchase_order_id,s.name,p.name,pr.received_quantity,
                   pr.unit_price,pr.total,pr.tax_amount,pr.grand_total
            FROM purchase_receipts pr
            JOIN suppliers s ON s.id=pr.supplier_id
            JOIN products p ON p.id=pr.product_id
            WHERE pr.invoice_id IS NULL
            ORDER BY pr.id DESC
            """
        )
        open_receipts = cur.fetchall()
        conn.close()
        return render_template("purchase_invoice_from_receipt.html", open_receipts=open_receipts)

    return purchase_invoice_from_receipt
