from flask import flash, redirect, render_template, request, url_for


def _withholding_choices(table_name):
    if table_name == "suppliers":
        return [("taxable", "خاضع"), ("exempt", "معفي (دفعات مقدمة)")]
    return [("subject", "خاضع للخصم"), ("non_subject", "غير خاضع")]


def _read_party_form(table_name):
    default_status = "exempt" if table_name == "suppliers" else "non_subject"
    return {
        "name": request.form.get("name", "").strip(),
        "phone": request.form.get("phone", "").strip(),
        "address": request.form.get("address", "").strip(),
        "tax_registration_number": request.form.get("tax_registration_number", "").strip(),
        "tax_card_number": request.form.get("tax_card_number", "").strip(),
        "contact_person": request.form.get("contact_person", "").strip(),
        "email": request.form.get("email", "").strip(),
        "withholding_status": request.form.get("withholding_status", default_status).strip() or default_status,
    }


def _allowed_status(table_name, value):
    values = {item[0] for item in _withholding_choices(table_name)}
    return value if value in values else ("exempt" if table_name == "suppliers" else "non_subject")


def _reference_checks(table_name):
    if table_name == "customers":
        return [
            ("sales_invoices", "customer_id", "فواتير بيع"),
            ("financial_sales_invoices", "customer_id", "فواتير مالية"),
            ("receipt_vouchers", "customer_id", "سندات قبض"),
            ("customer_adjustments", "customer_id", "تسويات عملاء"),
            ("sales_orders", "customer_id", "أوامر بيع"),
            ("sales_delivery_notes", "customer_id", "أذون صرف"),
            ("sales_credit_notes", "customer_id", "إشعارات تسوية دائنة"),
        ]
    return [
        ("purchase_invoices", "supplier_id", "فواتير مورد"),
        ("payment_vouchers", "supplier_id", "سندات صرف"),
        ("purchase_orders", "supplier_id", "أوامر شراء"),
        ("purchase_receipts", "supplier_id", "أذون إضافة"),
        ("purchase_returns", "supplier_id", "مردودات مشتريات"),
        ("products", "default_supplier_id", "أصناف مرتبطة"),
    ]


def build_party_page(deps):
    db = deps["db"]
    log_action = deps["log_action"]

    def party_page(table_name, template_title, success_message):
        conn = db()
        cur = conn.cursor()

        if request.method == "POST":
            data = _read_party_form(table_name)
            data["withholding_status"] = _allowed_status(table_name, data["withholding_status"])
            if not data["name"]:
                flash("الاسم مطلوب.", "danger")
            else:
                cur.execute(
                    f"""
                    INSERT INTO {table_name}(
                        name,phone,address,tax_registration_number,tax_card_number,
                        contact_person,email,withholding_status
                    )
                    VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (
                        data["name"],
                        data["phone"],
                        data["address"],
                        data["tax_registration_number"],
                        data["tax_card_number"],
                        data["contact_person"],
                        data["email"],
                        data["withholding_status"],
                    ),
                )
                party_id = cur.lastrowid
                log_action(cur, "create", table_name[:-1], party_id, data["name"])
                conn.commit()
                conn.close()
                flash(success_message, "success")
                return redirect(url_for(table_name))

        filters = {
            "q": (request.args.get("q") or "").strip(),
            "withholding_status": (request.args.get("withholding_status") or "").strip(),
        }
        where = []
        params = []
        if filters["q"]:
            where.append("(name LIKE ? OR phone LIKE ? OR tax_registration_number LIKE ? OR tax_card_number LIKE ?)")
            params.extend([f"%{filters['q']}%"] * 4)
        allowed_statuses = {choice[0] for choice in _withholding_choices(table_name)}
        if filters["withholding_status"] in allowed_statuses:
            where.append("withholding_status = ?")
            params.append(filters["withholding_status"])
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        cur.execute(
            f"""
            SELECT id,name,phone,address,tax_registration_number,tax_card_number,contact_person,email,withholding_status
            FROM {table_name}
            {where_sql}
            ORDER BY id DESC
            """,
            params,
        )
        rows = cur.fetchall()
        conn.close()
        return render_template(
            "parties.html",
            title=template_title,
            rows=rows,
            endpoint=table_name,
            withholding_choices=_withholding_choices(table_name),
            filters=filters,
        )

    return party_page


def build_party_edit_view(deps):
    db = deps["db"]
    log_action = deps["log_action"]
    row_snapshot = deps["row_snapshot"]

    def party_edit(table_name, entity_label, party_id):
        conn = db()
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT id,name,phone,address,tax_registration_number,tax_card_number,contact_person,email,withholding_status
            FROM {table_name}
            WHERE id=?
            """,
            (party_id,),
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            flash(f"{entity_label} غير موجود.", "danger")
            return redirect(url_for(table_name))

        if request.method == "POST":
            data = _read_party_form(table_name)
            data["withholding_status"] = _allowed_status(table_name, data["withholding_status"])
            if not data["name"]:
                flash("الاسم مطلوب.", "danger")
            else:
                before = row_snapshot(cur, table_name, party_id)
                cur.execute(
                    f"""
                    UPDATE {table_name}
                    SET name=?,phone=?,address=?,tax_registration_number=?,tax_card_number=?,
                        contact_person=?,email=?,withholding_status=?
                    WHERE id=?
                    """,
                    (
                        data["name"],
                        data["phone"],
                        data["address"],
                        data["tax_registration_number"],
                        data["tax_card_number"],
                        data["contact_person"],
                        data["email"],
                        data["withholding_status"],
                        party_id,
                    ),
                )
                after = row_snapshot(cur, table_name, party_id)
                log_action(cur, "update", table_name[:-1], party_id, f"تعديل {entity_label}", before, after)
                conn.commit()
                conn.close()
                flash(f"تم تعديل بيانات {entity_label}.", "success")
                return redirect(url_for(table_name))

        conn.close()
        return render_template(
            "party_edit.html",
            endpoint=table_name,
            title=f"تعديل {entity_label}",
            row=row,
            withholding_choices=_withholding_choices(table_name),
        )

    return party_edit


def build_party_delete_view(deps):
    db = deps["db"]
    log_action = deps["log_action"]
    row_snapshot = deps["row_snapshot"]

    def party_delete(table_name, entity_label, party_id):
        conn = db()
        cur = conn.cursor()
        cur.execute(f"SELECT name FROM {table_name} WHERE id=?", (party_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            flash(f"{entity_label} غير موجود.", "danger")
            return redirect(url_for(table_name))

        for ref_table, column, label in _reference_checks(table_name):
            cur.execute(f"SELECT COUNT(*) FROM {ref_table} WHERE {column}=?", (party_id,))
            if cur.fetchone()[0]:
                conn.close()
                flash(f"لا يمكن حذف {entity_label} لوجود {label} مرتبطة به.", "danger")
                return redirect(url_for(table_name))

        before = row_snapshot(cur, table_name, party_id)
        cur.execute(f"DELETE FROM {table_name} WHERE id=?", (party_id,))
        log_action(cur, "delete", table_name[:-1], party_id, f"حذف {entity_label}", before, None)
        conn.commit()
        conn.close()
        flash(f"تم حذف {entity_label}.", "success")
        return redirect(url_for(table_name))

    return party_delete


def build_customers_view(deps):
    party_page = build_party_page(deps)

    def customers():
        return party_page("customers", "العملاء", "تمت إضافة العميل بنجاح.")

    return customers


def build_suppliers_view(deps):
    party_page = build_party_page(deps)

    def suppliers():
        return party_page("suppliers", "الموردون", "تمت إضافة المورد بنجاح.")

    return suppliers
