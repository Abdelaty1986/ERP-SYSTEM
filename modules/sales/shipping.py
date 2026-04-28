from flask import flash, redirect, render_template, request, url_for


def _refresh_sales_order_status(cur, sales_order_id):
    if not sales_order_id:
        return
    cur.execute(
        """
        SELECT COALESCE(SUM(quantity),0)
        FROM sales_order_lines
        WHERE order_id=?
        """,
        (sales_order_id,),
    )
    ordered_total = cur.fetchone()[0] or 0
    cur.execute(
        """
        SELECT COALESCE(SUM(delivered_quantity),0)
        FROM sales_delivery_notes
        WHERE sales_order_id=?
          AND status!='cancelled'
        """,
        (sales_order_id,),
    )
    delivered_total = cur.fetchone()[0] or 0
    if delivered_total <= 0:
        status = "issued"
    elif delivered_total >= ordered_total:
        status = "completed"
    else:
        status = "partial"
    cur.execute("UPDATE sales_orders SET status=? WHERE id=?", (status, sales_order_id))


def _refresh_purchase_order_status(cur, purchase_order_id):
    if not purchase_order_id:
        return
    cur.execute(
        """
        SELECT COALESCE(SUM(quantity),0)
        FROM purchase_order_lines
        WHERE order_id=?
        """,
        (purchase_order_id,),
    )
    ordered_total = cur.fetchone()[0] or 0
    cur.execute(
        """
        SELECT COALESCE(SUM(received_quantity),0)
        FROM purchase_receipts
        WHERE purchase_order_id=?
          AND status!='cancelled'
        """,
        (purchase_order_id,),
    )
    received_total = cur.fetchone()[0] or 0
    if received_total <= 0:
        status = "issued"
    elif received_total >= ordered_total:
        status = "completed"
    else:
        status = "partial"
    cur.execute("UPDATE purchase_orders SET status=? WHERE id=?", (status, purchase_order_id))


def build_sales_deliveries_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    parse_iso_date = deps["parse_iso_date"]
    ensure_open_period = deps["ensure_open_period"]
    next_document_number = deps["next_document_number"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]

    def sales_deliveries():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            line_id = int(parse_positive_amount(request.form.get("sales_order_line_id")) or 0)
            delivered_quantity = parse_positive_amount(request.form.get("delivered_quantity"))
            notes = request.form.get("notes", "").strip()
            cur.execute(
                """
                SELECT so.id,sol.id,so.customer_id,sol.product_id,sol.quantity,sol.unit_price,sol.tax_rate,
                       p.name,p.purchase_price,p.stock_quantity,so.date,so.delivery_date
                FROM sales_order_lines sol
                JOIN sales_orders so ON so.id=sol.order_id
                JOIN products p ON p.id=sol.product_id
                WHERE sol.id=?
                """,
                (line_id,),
            )
            order = cur.fetchone()
            cur.execute(
                """
                SELECT COALESCE(SUM(delivered_quantity),0)
                FROM sales_delivery_notes
                WHERE sales_order_line_id=?
                  AND status!='cancelled'
                """,
                (line_id,),
            )
            already_delivered = cur.fetchone()[0] if order else 0
            remaining = (order[4] - already_delivered) if order else 0
            movement_date = parse_iso_date(date_value)
            order_date = parse_iso_date(order[10]) if order else None
            planned_delivery_date = parse_iso_date(order[11]) if order else None
            if not date_value:
                flash("تاريخ إذن الصرف مطلوب.", "danger")
            elif not order:
                flash("بند أمر البيع غير موجود.", "danger")
            elif movement_date and order_date and movement_date < order_date:
                flash("تاريخ إذن الصرف لا يمكن أن يكون أسبق من تاريخ أمر البيع.", "danger")
            elif movement_date and planned_delivery_date and movement_date < planned_delivery_date:
                flash("تاريخ إذن الصرف لا يمكن أن يكون أسبق من تاريخ التسليم المحدد في أمر البيع.", "danger")
            elif delivered_quantity <= 0 or delivered_quantity > remaining:
                flash("الكمية المنصرفة يجب أن تكون أكبر من صفر ولا تتجاوز الكمية المتبقية.", "danger")
            elif delivered_quantity > order[9]:
                flash("رصيد المخزون لا يكفي لإذن الصرف.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("sales_deliveries"))
                delivery_no = next_document_number(cur, "sales_delivery_notes")
                total = delivered_quantity * order[5]
                cost_total = delivered_quantity * order[8]
                tax_amount = total * order[6] / 100
                grand_total = total + tax_amount
                cogs_journal_id = (
                    create_auto_journal(cur, date_value, f"إذن صرف مبيعات {delivery_no} - {order[7]}", "6100", "1400", cost_total)
                    if cost_total > 0
                    else None
                )
                cur.execute(
                    """
                    INSERT INTO sales_delivery_notes(
                        delivery_no,date,sales_order_id,sales_order_line_id,customer_id,product_id,
                        ordered_quantity,delivered_quantity,unit_price,total,cost_total,tax_rate,
                        tax_amount,grand_total,cogs_journal_id,notes
                    )
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        delivery_no,
                        date_value,
                        order[0],
                        order[1],
                        order[2],
                        order[3],
                        order[4],
                        delivered_quantity,
                        order[5],
                        total,
                        cost_total,
                        order[6],
                        tax_amount,
                        grand_total,
                        cogs_journal_id,
                        notes,
                    ),
                )
                delivery_id = cur.lastrowid
                mark_journal_source(cur, "sales_delivery", delivery_id, cogs_journal_id)
                cur.execute("UPDATE products SET stock_quantity=stock_quantity-? WHERE id=?", (delivered_quantity, order[3]))
                cur.execute(
                    """
                    INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (date_value, order[3], "out", -delivered_quantity, "sales_delivery", delivery_id, f"إذن صرف {delivery_no}"),
                )
                _refresh_sales_order_status(cur, order[0])
                log_action(cur, "create", "sales_delivery", delivery_id, f"{delivery_no}; total={grand_total}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash(f"تم تسجيل إذن الصرف {delivery_no}.", "success")
                return redirect(url_for("sales_deliveries"))

        cur.execute(
            """
            SELECT sol.id,so.id,so.date,COALESCE(c.name,'بيع نقدي'),p.name,COALESCE(p.code,''),COALESCE(p.barcode_value,''),
                   sol.quantity,sol.unit_price,sol.quantity-COALESCE(SUM(CASE WHEN sd.status!='cancelled' THEN sd.delivered_quantity ELSE 0 END),0) AS remaining
            FROM sales_order_lines sol
            JOIN sales_orders so ON so.id=sol.order_id
            LEFT JOIN customers c ON c.id=so.customer_id
            JOIN products p ON p.id=sol.product_id
            LEFT JOIN sales_delivery_notes sd ON sd.sales_order_line_id=sol.id
            GROUP BY sol.id
            HAVING remaining > 0
            ORDER BY so.id DESC, sol.id
            """
        )
        open_orders = cur.fetchall()
        cur.execute(
            """
            SELECT sd.id,sd.delivery_no,sd.date,sd.sales_order_id,COALESCE(c.name,'بيع نقدي'),p.name,
                   sd.delivered_quantity,sd.unit_price,sd.grand_total,sd.invoice_id,sd.status,COALESCE(sd.cancel_reason,'')
            FROM sales_delivery_notes sd
            LEFT JOIN customers c ON c.id=sd.customer_id
            JOIN products p ON p.id=sd.product_id
            ORDER BY sd.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("sales_deliveries.html", open_orders=open_orders, rows=rows)

    return sales_deliveries


def build_purchase_receipts_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    parse_iso_date = deps["parse_iso_date"]
    ensure_open_period = deps["ensure_open_period"]
    next_document_number = deps["next_document_number"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]

    def purchase_receipts():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            line_id = int(parse_positive_amount(request.form.get("purchase_order_line_id")) or 0)
            received_quantity = parse_positive_amount(request.form.get("received_quantity"))
            notes = request.form.get("notes", "").strip()
            cur.execute(
                """
                SELECT po.id,pol.id,po.supplier_id,pol.product_id,pol.quantity,pol.unit_price,pol.tax_rate,p.name,po.date,po.delivery_date
                FROM purchase_order_lines pol
                JOIN purchase_orders po ON po.id=pol.order_id
                JOIN products p ON p.id=pol.product_id
                WHERE pol.id=?
                """,
                (line_id,),
            )
            order = cur.fetchone()
            cur.execute(
                """
                SELECT COALESCE(SUM(received_quantity),0)
                FROM purchase_receipts
                WHERE purchase_order_line_id=?
                  AND status!='cancelled'
                """,
                (line_id,),
            )
            already_received = cur.fetchone()[0] if order else 0
            remaining = (order[4] - already_received) if order else 0
            movement_date = parse_iso_date(date_value)
            order_date = parse_iso_date(order[8]) if order else None
            planned_supply_date = parse_iso_date(order[9]) if order else None
            if not date_value:
                flash("تاريخ إذن الإضافة مطلوب.", "danger")
            elif not order:
                flash("بند أمر الشراء غير موجود.", "danger")
            elif movement_date and order_date and movement_date < order_date:
                flash("تاريخ إذن الإضافة لا يمكن أن يكون أسبق من تاريخ أمر الشراء.", "danger")
            elif movement_date and planned_supply_date and movement_date < planned_supply_date:
                flash("تاريخ إذن الإضافة لا يمكن أن يكون أسبق من تاريخ التوريد المحدد في أمر الشراء.", "danger")
            elif received_quantity <= 0 or received_quantity > remaining:
                flash("الكمية المستلمة يجب أن تكون أكبر من صفر ولا تتجاوز الكمية المتبقية.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("purchase_receipts"))
                receipt_no = next_document_number(cur, "purchase_receipts")
                total = received_quantity * order[5]
                tax_amount = total * order[6] / 100
                grand_total = total + tax_amount
                journal_id = create_auto_journal(cur, date_value, f"إذن إضافة مخزني {receipt_no} - {order[7]}", "1400", "2150", total)
                cur.execute(
                    """
                    INSERT INTO purchase_receipts(
                        receipt_no,date,purchase_order_id,purchase_order_line_id,supplier_id,product_id,
                        ordered_quantity,received_quantity,unit_price,total,tax_rate,tax_amount,grand_total,journal_id,notes
                    )
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        receipt_no,
                        date_value,
                        order[0],
                        order[1],
                        order[2],
                        order[3],
                        order[4],
                        received_quantity,
                        order[5],
                        total,
                        order[6],
                        tax_amount,
                        grand_total,
                        journal_id,
                        notes,
                    ),
                )
                receipt_id = cur.lastrowid
                mark_journal_source(cur, "purchase_receipt", receipt_id, journal_id)
                cur.execute("UPDATE products SET stock_quantity=stock_quantity+?, purchase_price=? WHERE id=?", (received_quantity, order[5], order[3]))
                cur.execute(
                    """
                    INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (date_value, order[3], "in", received_quantity, "purchase_receipt", receipt_id, f"إذن إضافة {receipt_no}"),
                )
                _refresh_purchase_order_status(cur, order[0])
                log_action(cur, "create", "purchase_receipt", receipt_id, f"{receipt_no}; total={grand_total}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash(f"تم تسجيل إذن الإضافة {receipt_no}.", "success")
                return redirect(url_for("purchase_receipts"))

        cur.execute(
            """
            SELECT pol.id,po.id,po.date,s.name,p.name,pol.quantity,pol.unit_price,
                   pol.quantity-COALESCE(SUM(CASE WHEN pr.status!='cancelled' THEN pr.received_quantity ELSE 0 END),0) AS remaining
            FROM purchase_order_lines pol
            JOIN purchase_orders po ON po.id=pol.order_id
            JOIN suppliers s ON s.id=po.supplier_id
            JOIN products p ON p.id=pol.product_id
            LEFT JOIN purchase_receipts pr ON pr.purchase_order_line_id=pol.id
            GROUP BY pol.id
            HAVING remaining > 0
            ORDER BY po.id DESC, pol.id
            """
        )
        open_orders = cur.fetchall()
        cur.execute(
            """
            SELECT pr.id,pr.receipt_no,pr.date,pr.purchase_order_id,s.name,p.name,
                   pr.received_quantity,pr.unit_price,pr.grand_total,pr.invoice_id,pr.status,COALESCE(pr.cancel_reason,'')
            FROM purchase_receipts pr
            JOIN suppliers s ON s.id=pr.supplier_id
            JOIN products p ON p.id=pr.product_id
            ORDER BY pr.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("purchase_receipts.html", open_orders=open_orders, rows=rows)

    return purchase_receipts


def build_cancel_sales_delivery_view(deps):
    db = deps["db"]
    reverse_journal = deps["reverse_journal"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]

    def cancel_sales_delivery(id):
        reason = request.form.get("reason", "").strip() or "إلغاء إذن صرف"
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id,delivery_no,date,sales_order_id,product_id,delivered_quantity,cogs_journal_id,status,invoice_id
            FROM sales_delivery_notes
            WHERE id=?
            """,
            (id,),
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            flash("إذن الصرف غير موجود.", "danger")
            return redirect(url_for("sales_deliveries"))
        delivery_id, delivery_no, date_value, sales_order_id, product_id, quantity, cogs_journal_id, status, invoice_id = row
        if status == "cancelled":
            conn.close()
            flash("إذن الصرف ملغى مسبقًا.", "warning")
            return redirect(url_for("sales_deliveries"))
        if invoice_id:
            conn.close()
            flash("لا يمكن إلغاء إذن الصرف بعد فوترته. ألغِ فاتورة البيع المرتبطة أولًا.", "danger")
            return redirect(url_for("sales_deliveries"))
        reverse_journal(cur, cogs_journal_id, date_value, reason)
        cur.execute("UPDATE products SET stock_quantity=stock_quantity+? WHERE id=?", (quantity, product_id))
        cur.execute(
            """
            INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes)
            VALUES (?,?,?,?,?,?,?)
            """,
            (date_value, product_id, "cancel_in", quantity, "sales_delivery_cancel", delivery_id, reason),
        )
        cur.execute(
            """
            UPDATE sales_delivery_notes
            SET status='cancelled', invoice_id=NULL, cancelled_at=CURRENT_TIMESTAMP, cancel_reason=?
            WHERE id=?
            """,
            (reason, delivery_id),
        )
        _refresh_sales_order_status(cur, sales_order_id)
        log_action(cur, "cancel", "sales_delivery", delivery_id, f"{delivery_no}; {reason}")
        conn.commit()
        conn.close()
        rebuild_ledger()
        flash("تم إلغاء إذن الصرف وعكس أثر المخزون والتكلفة.", "success")
        return redirect(url_for("sales_deliveries"))

    return cancel_sales_delivery


def build_cancel_purchase_receipt_view(deps):
    db = deps["db"]
    reverse_journal = deps["reverse_journal"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]

    def cancel_purchase_receipt(id):
        reason = request.form.get("reason", "").strip() or "إلغاء إذن استلام"
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id,receipt_no,date,purchase_order_id,product_id,received_quantity,journal_id,status,invoice_id
            FROM purchase_receipts
            WHERE id=?
            """,
            (id,),
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            flash("إذن الاستلام غير موجود.", "danger")
            return redirect(url_for("purchase_receipts"))
        receipt_id, receipt_no, date_value, purchase_order_id, product_id, quantity, journal_id, status, invoice_id = row
        if status == "cancelled":
            conn.close()
            flash("إذن الاستلام ملغى مسبقًا.", "warning")
            return redirect(url_for("purchase_receipts"))
        if invoice_id:
            conn.close()
            flash("لا يمكن إلغاء إذن الاستلام بعد فوترته. ألغِ فاتورة المشتريات المرتبطة أولًا.", "danger")
            return redirect(url_for("purchase_receipts"))
        cur.execute("SELECT stock_quantity FROM products WHERE id=?", (product_id,))
        stock_row = cur.fetchone()
        if not stock_row or (stock_row[0] or 0) < quantity:
            conn.close()
            flash("لا يمكن إلغاء إذن الاستلام لأن رصيد المخزون الحالي لا يكفي لعكس الحركة.", "danger")
            return redirect(url_for("purchase_receipts"))
        reverse_journal(cur, journal_id, date_value, reason)
        cur.execute("UPDATE products SET stock_quantity=stock_quantity-? WHERE id=?", (quantity, product_id))
        cur.execute(
            """
            INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes)
            VALUES (?,?,?,?,?,?,?)
            """,
            (date_value, product_id, "cancel_out", -quantity, "purchase_receipt_cancel", receipt_id, reason),
        )
        cur.execute(
            """
            UPDATE purchase_receipts
            SET status='cancelled', invoice_id=NULL, cancelled_at=CURRENT_TIMESTAMP, cancel_reason=?
            WHERE id=?
            """,
            (reason, receipt_id),
        )
        _refresh_purchase_order_status(cur, purchase_order_id)
        log_action(cur, "cancel", "purchase_receipt", receipt_id, f"{receipt_no}; {reason}")
        conn.commit()
        conn.close()
        rebuild_ledger()
        flash("تم إلغاء إذن الاستلام وعكس أثر المخزون.", "success")
        return redirect(url_for("purchase_receipts"))

    return cancel_purchase_receipt
