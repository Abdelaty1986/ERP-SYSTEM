import json

import sqlite3

from flask import flash, redirect, render_template, request, url_for
from modules.sales.taxing import invoice_totals, parse_flag, taxable_line
from modules.accounting.ledger_engine import post_entries
from modules.sales.advanced import (
    build_financial_sales_view,
    build_purchase_invoice_from_receipt_view,
    build_sales_invoice_from_delivery_view,
)
from modules.sales.documents import (
    build_prepare_sales_credit_note_einvoice_view,
    build_print_purchase_view,
    build_print_sale_view,
    build_print_sales_credit_note_view,
)
from modules.sales.orders import (
    build_print_purchase_order_view,
    build_purchase_orders_view,
    build_sales_orders_view,
)
from modules.sales.shipping import (
    build_purchase_receipts_view,
    build_sales_deliveries_view,
)
from modules.sales.returns import (
    build_purchase_returns_view,
    build_sales_credit_notes_view,
    build_sales_returns_view,
)
from modules.sales.statements import build_customer_statement_view, build_supplier_statement_view
from modules.sales.treasury import (
    build_customer_adjustments_view,
    build_payments_view,
    build_prepare_customer_adjustment_einvoice_view,
    build_print_customer_adjustment_view,
    build_print_payment_view,
    build_print_receipt_view,
    build_receipts_view,
)


def _order_lines_from_form(cur, deps):
    parse_positive_amount = deps["parse_positive_amount"]
    default_tax_rate = deps["DEFAULT_TAX_RATE"]
    product_ids = request.form.getlist("product_id[]") or request.form.getlist("product_id")
    quantities = request.form.getlist("quantity[]") or request.form.getlist("quantity")
    unit_prices = request.form.getlist("unit_price[]") or request.form.getlist("unit_price")
    tax_rates = request.form.getlist("tax_rate[]") or request.form.getlist("tax_rate")
    lines = []
    for idx, product_id in enumerate(product_ids):
        product_id = (product_id or "").strip()
        quantity = parse_positive_amount(quantities[idx] if idx < len(quantities) else 0)
        unit_price = parse_positive_amount(unit_prices[idx] if idx < len(unit_prices) else 0)
        tax_rate = parse_positive_amount(tax_rates[idx] if idx < len(tax_rates) else default_tax_rate)
        if not product_id and quantity == 0 and unit_price == 0:
            continue
        cur.execute("SELECT 1 FROM products WHERE id=?", (product_id,))
        if not cur.fetchone() or quantity <= 0 or unit_price <= 0:
            return []
        total = quantity * unit_price
        tax_amount = total * tax_rate / 100
        lines.append((int(product_id), quantity, unit_price, total, tax_rate, tax_amount, total + tax_amount))
    return lines


def _single_line_tax_selection(form, default_tax_rate, default_withholding_rate):
    vat_rate = float(form.get("vat_rate", form.get("tax_rate", default_tax_rate)) or 0)
    withholding_rate = float(form.get("withholding_rate", default_withholding_rate) or 0)
    vat_enabled = parse_flag(form.get("vat_enabled"), True)
    withholding_enabled = parse_flag(form.get("withholding_enabled"), default_withholding_rate > 0)
    return vat_enabled, withholding_enabled, vat_rate, withholding_rate


def _invoice_product_options(cur, invoice_type, invoice_id):
    if invoice_type == "sales":
        cur.execute(
            """
            SELECT sil.product_id,p.name,sil.quantity,sil.unit_price,
                   COALESCE((SELECT SUM(quantity) FROM sales_returns sr WHERE sr.sales_invoice_id=sil.invoice_id AND sr.product_id=sil.product_id),0)
            FROM sales_invoice_lines sil
            JOIN products p ON p.id=sil.product_id
            WHERE sil.invoice_id=?
            ORDER BY sil.id
            """,
            (invoice_id,),
        )
        rows = cur.fetchall()
        if not rows:
            cur.execute(
                """
                SELECT s.product_id,p.name,s.quantity,s.unit_price,
                       COALESCE((SELECT SUM(quantity) FROM sales_returns sr WHERE sr.sales_invoice_id=s.id AND sr.product_id=s.product_id),0)
                FROM sales_invoices s
                JOIN products p ON p.id=s.product_id
                WHERE s.id=?
                """,
                (invoice_id,),
            )
            rows = cur.fetchall()
    else:
        cur.execute(
            """
            SELECT pil.product_id,p.name,pil.quantity,pil.unit_price,
                   COALESCE((SELECT SUM(quantity) FROM purchase_returns pr WHERE pr.purchase_invoice_id=pil.invoice_id AND pr.product_id=pil.product_id),0)
            FROM purchase_invoice_lines pil
            JOIN products p ON p.id=pil.product_id
            WHERE pil.invoice_id=?
            ORDER BY pil.id
            """,
            (invoice_id,),
        )
        rows = cur.fetchall()
        if not rows:
            cur.execute(
                """
                SELECT p.product_id,pr.name,p.quantity,p.unit_price,
                       COALESCE((SELECT SUM(quantity) FROM purchase_returns rr WHERE rr.purchase_invoice_id=p.id AND rr.product_id=p.product_id),0)
                FROM purchase_invoices p
                JOIN products pr ON pr.id=p.product_id
                WHERE p.id=?
                """,
                (invoice_id,),
            )
            rows = cur.fetchall()
    result = []
    for product_id, name, quantity, unit_price, returned_qty in rows:
        available = max((quantity or 0) - (returned_qty or 0), 0)
        result.append(
            {
                "product_id": product_id,
                "name": name,
                "quantity": quantity or 0,
                "unit_price": unit_price or 0,
                "available": available,
            }
        )
    return invoice_id, result


def _customer_withholding(cur, customer_id):
    if not customer_id:
        return "non_subject", 0
    cur.execute("SELECT withholding_status FROM customers WHERE id=?", (customer_id,))
    row = cur.fetchone()
    status = (row[0] if row else "non_subject") or "non_subject"
    return status, (1 if status == "subject" else 0)


def _supplier_withholding(cur, supplier_id):
    if not supplier_id:
        return "exempt", 0
    cur.execute("SELECT withholding_status FROM suppliers WHERE id=?", (supplier_id,))
    row = cur.fetchone()
    status = (row[0] if row else "exempt") or "exempt"
    return status, (1 if status == "taxable" else 0)


def _ensure_product_unit_mapping(cur, product_id):
    cur.execute("SELECT unit,purchase_price,sale_price FROM products WHERE id=?", (product_id,))
    product = cur.fetchone()
    if not product:
        return
    cur.execute("SELECT COUNT(*) FROM product_units WHERE product_id=?", (product_id,))
    if cur.fetchone()[0]:
        return
    cur.execute(
        """
        INSERT OR IGNORE INTO measurement_units(name, code, description, is_active)
        VALUES ('وحدة','UNIT','وحدة عامة للاستخدام الافتراضي',1)
        """
    )
    cur.execute("SELECT id FROM measurement_units WHERE name='وحدة'")
    unit_id = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO product_units(
            product_id,unit_id,conversion_factor,purchase_price,sale_price,
            is_default_purchase,is_default_sale,is_base_unit,is_active
        )
        VALUES (?,?,?,?,?,1,1,1,1)
        """,
        (product_id, unit_id, 1, float(product[1] or 0), float(product[2] or 0)),
    )
    cur.execute("UPDATE products SET unit=? WHERE id=?", (product[0] or "وحدة", product_id))


def _resolve_product_unit(cur, product_id, selected_unit_id=None, purpose="sale"):
    _ensure_product_unit_mapping(cur, product_id)
    order_column = "pu.is_default_sale" if purpose == "sale" else "pu.is_default_purchase"
    params = [product_id]
    selected_clause = ""
    if selected_unit_id:
        selected_clause = " AND pu.unit_id=?"
        params.append(int(selected_unit_id))
    cur.execute(
        f"""
        SELECT pu.unit_id,mu.name,pu.conversion_factor,pu.purchase_price,pu.sale_price,
               pu.is_default_purchase,pu.is_default_sale,pu.is_base_unit
        FROM product_units pu
        JOIN measurement_units mu ON mu.id=pu.unit_id
        WHERE pu.product_id=? AND pu.is_active=1{selected_clause}
        ORDER BY {order_column} DESC, pu.is_base_unit DESC, pu.id ASC
        LIMIT 1
        """,
        params,
    )
    row = cur.fetchone()
    if row:
        return {
            "unit_id": row[0],
            "unit_name": row[1],
            "conversion_factor": float(row[2] or 1),
            "purchase_price": float(row[3] or 0),
            "sale_price": float(row[4] or 0),
            "is_default_purchase": bool(row[5]),
            "is_default_sale": bool(row[6]),
            "is_base_unit": bool(row[7]),
        }
    return {
        "unit_id": None,
        "unit_name": "وحدة",
        "conversion_factor": 1.0,
        "purchase_price": 0.0,
        "sale_price": 0.0,
        "is_default_purchase": True,
        "is_default_sale": True,
        "is_base_unit": True,
    }


def _build_product_units_map(cur, purpose="sale"):
    cur.execute("SELECT id,name,stock_quantity,purchase_price,sale_price FROM products ORDER BY name")
    raw_product_rows = cur.fetchall()
    product_rows = []
    data = {}
    for product_id, name, stock_quantity, purchase_price, sale_price in raw_product_rows:
        _ensure_product_unit_mapping(cur, product_id)
        cur.execute(
            """
            SELECT pu.unit_id,mu.name,pu.conversion_factor,pu.purchase_price,pu.sale_price,
                   pu.is_default_purchase,pu.is_default_sale,pu.is_base_unit
            FROM product_units pu
            JOIN measurement_units mu ON mu.id=pu.unit_id
            WHERE pu.product_id=? AND pu.is_active=1
            ORDER BY pu.is_base_unit DESC, pu.conversion_factor ASC, pu.id ASC
            """,
            (product_id,),
        )
        units = []
        default_unit_id = None
        for row in cur.fetchall():
            unit = {
                "unit_id": row[0],
                "unit_name": row[1],
                "conversion_factor": float(row[2] or 1),
                "purchase_price": float(row[3] or purchase_price or 0),
                "sale_price": float(row[4] or sale_price or 0),
                "is_default_purchase": bool(row[5]),
                "is_default_sale": bool(row[6]),
                "is_base_unit": bool(row[7]),
            }
            if purpose == "sale" and unit["is_default_sale"]:
                default_unit_id = unit["unit_id"]
            if purpose == "purchase" and unit["is_default_purchase"]:
                default_unit_id = unit["unit_id"]
            units.append(unit)
        if units and default_unit_id is None:
            default_unit_id = units[0]["unit_id"]
        product_rows.append(
            (
                product_id,
                name,
                float(sale_price or 0) if purpose == "sale" else float(purchase_price or 0),
                float(stock_quantity or 0),
            )
        )
        data[str(product_id)] = {
            "product_id": product_id,
            "name": name,
            "stock_quantity": float(stock_quantity or 0),
            "default_unit_id": default_unit_id,
            "units": units,
        }
    return product_rows, data


def _existing_invoice_for_order(cur, invoice_table, order_column, order_id):
    if not order_id:
        return None
    cur.execute(
        f"""
        SELECT id, doc_no, status
        FROM {invoice_table}
        WHERE {order_column}=?
          AND COALESCE(status, 'draft') != 'cancelled'
        ORDER BY id DESC
        LIMIT 1
        """,
        (order_id,),
    )
    return cur.fetchone()


def _invoice_form_lines(cur, deps, purpose="sale", vat_rate=14, withholding_rate=0, withholding_enabled=False):
    parse_positive_amount = deps["parse_positive_amount"]
    product_ids = request.form.getlist("product_id[]") or request.form.getlist("product_id")
    unit_ids = request.form.getlist("unit_id[]") or request.form.getlist("unit_id")
    quantities = request.form.getlist("quantity[]") or request.form.getlist("quantity")
    unit_prices = request.form.getlist("unit_price[]") or request.form.getlist("unit_price")
    lines = []
    for idx, raw_product_id in enumerate(product_ids):
        product_id = int(parse_positive_amount(raw_product_id) or 0)
        unit_id = int(parse_positive_amount(unit_ids[idx] if idx < len(unit_ids) else 0) or 0) or None
        quantity = parse_positive_amount(quantities[idx] if idx < len(quantities) else 0)
        unit_price = parse_positive_amount(unit_prices[idx] if idx < len(unit_prices) else 0)
        if product_id <= 0 and quantity <= 0 and unit_price <= 0:
            continue
        cur.execute("SELECT name, stock_quantity, purchase_price FROM products WHERE id=?", (product_id,))
        product = cur.fetchone()
        if not product or quantity <= 0 or unit_price <= 0:
            return []
        unit_meta = _resolve_product_unit(cur, product_id, unit_id, purpose)
        quantity_base = round(quantity * float(unit_meta["conversion_factor"] or 1), 4)
        line = taxable_line(
            quantity * unit_price,
            vat_enabled=True,
            withholding_enabled=withholding_enabled,
            vat_rate=vat_rate,
            withholding_rate=withholding_rate,
        )
        lines.append(
            {
                "product_id": product_id,
                "product_name": product[0],
                "stock_quantity": float(product[1] or 0),
                "purchase_price": float(product[2] or 0),
                "quantity": quantity,
                "unit_price": unit_price,
                "total": line["subtotal"],
                "tax_rate": line["vat_rate"],
                "tax_amount": line["vat_amount"],
                "withholding_rate": line["withholding_rate"],
                "withholding_amount": line["withholding_amount"],
                "grand_total": line["grand_total"],
                "unit_id": unit_meta["unit_id"],
                "unit_name": unit_meta["unit_name"],
                "selected_unit": unit_meta["unit_name"],
                "conversion_factor": float(unit_meta["conversion_factor"] or 1),
                "quantity_base": quantity_base,
                "cost_total": round(quantity_base * float(product[2] or 0), 2) if purpose == "sale" else 0,
            }
        )
    return lines


def _group_requested_base_qty(lines):
    grouped = {}
    for line in lines:
        product_id = int(line["product_id"])
        grouped[product_id] = round(grouped.get(product_id, 0) + float(line.get("quantity_base") or 0), 4)
    return grouped


def _has_enough_stock_for_lines(lines):
    grouped = _group_requested_base_qty(lines)
    for line in lines:
        product_id = int(line["product_id"])
        available = float(line.get("stock_quantity") or 0)
        if available < grouped.get(product_id, 0):
            return False
    return True


def _invoice_number_exists(cur, table_name, invoice_number, exclude_id=None):
    invoice_number = (invoice_number or "").strip()
    if not invoice_number:
        return False
    conditions = ["NULLIF(TRIM(COALESCE(invoice_number, '')), '') = ?"]
    params = [invoice_number]
    if exclude_id is not None:
        conditions.append("id <> ?")
        params.append(exclude_id)
    cur.execute(
        f"SELECT 1 FROM {table_name} WHERE {' AND '.join(conditions)} LIMIT 1",
        params,
    )
    return cur.fetchone() is not None


def _sales_order_invoice_payload(cur, order_id, vat_rate, withholding_rate, withholding_enabled):
    cur.execute(
        """
        SELECT so.id,so.customer_id,so.delivery_date,COALESCE(so.notes,''),sol.product_id,p.name,
               sol.quantity,COALESCE(sol.unit_id, NULL),COALESCE(sol.unit_name, p.unit, 'وحدة'),
               COALESCE(NULLIF(sol.conversion_factor, 0), 1),COALESCE(sol.quantity_base, sol.quantity),
               sol.unit_price,COALESCE(p.stock_quantity, 0),COALESCE(p.purchase_price, 0)
        FROM sales_orders so
        JOIN sales_order_lines sol ON sol.order_id=so.id
        JOIN products p ON p.id=sol.product_id
        WHERE so.id=?
        ORDER BY sol.id
        """,
        (order_id,),
    )
    rows = cur.fetchall()
    if not rows:
        return None, []
    header = {
        "order_id": rows[0][0],
        "customer_id": rows[0][1],
        "due_date": rows[0][2] or "",
        "notes": rows[0][3] or "",
    }
    lines = []
    for row in rows:
        line = taxable_line(
            row[11] * row[6],
            vat_enabled=True,
            withholding_enabled=withholding_enabled,
            vat_rate=vat_rate,
            withholding_rate=withholding_rate,
        )
        lines.append(
            {
                "product_id": row[4],
                "product_name": row[5],
                "quantity": float(row[6] or 0),
                "unit_id": row[7],
                "unit_name": row[8],
                "selected_unit": row[8],
                "conversion_factor": float(row[9] or 1),
                "quantity_base": float(row[10] or row[6] or 0),
                "unit_price": float(row[11] or 0),
                "stock_quantity": float(row[12] or 0),
                "purchase_price": float(row[13] or 0),
                "total": line["subtotal"],
                "tax_rate": line["vat_rate"],
                "tax_amount": line["vat_amount"],
                "withholding_rate": line["withholding_rate"],
                "withholding_amount": line["withholding_amount"],
                "grand_total": line["grand_total"],
                "cost_total": round(float(row[10] or row[6] or 0) * float(row[13] or 0), 2),
            }
        )
    return header, lines


def _purchase_order_invoice_payload(cur, order_id, vat_rate, withholding_rate, withholding_enabled):
    cur.execute(
        """
        SELECT po.id,po.supplier_id,po.delivery_date,COALESCE(po.notes,''),pol.product_id,p.name,
               pol.quantity,COALESCE(pol.unit_id, NULL),COALESCE(pol.unit_name, p.unit, 'وحدة'),
               COALESCE(NULLIF(pol.conversion_factor, 0), 1),COALESCE(pol.quantity_base, pol.quantity),
               pol.unit_price
        FROM purchase_orders po
        JOIN purchase_order_lines pol ON pol.order_id=po.id
        JOIN products p ON p.id=pol.product_id
        WHERE po.id=?
        ORDER BY pol.id
        """,
        (order_id,),
    )
    rows = cur.fetchall()
    if not rows:
        return None, []
    header = {
        "order_id": rows[0][0],
        "supplier_id": rows[0][1],
        "due_date": rows[0][2] or "",
        "notes": rows[0][3] or "",
    }
    lines = []
    for row in rows:
        line = taxable_line(
            row[11] * row[6],
            vat_enabled=True,
            withholding_enabled=withholding_enabled,
            vat_rate=vat_rate,
            withholding_rate=withholding_rate,
        )
        lines.append(
            {
                "product_id": row[4],
                "product_name": row[5],
                "quantity": float(row[6] or 0),
                "unit_id": row[7],
                "unit_name": row[8],
                "selected_unit": row[8],
                "conversion_factor": float(row[9] or 1),
                "quantity_base": float(row[10] or row[6] or 0),
                "unit_price": float(row[11] or 0),
                "total": line["subtotal"],
                "tax_rate": line["vat_rate"],
                "tax_amount": line["vat_amount"],
                "withholding_rate": line["withholding_rate"],
                "withholding_amount": line["withholding_amount"],
                "grand_total": line["grand_total"],
                "cost_total": 0,
            }
        )
    return header, lines


def _invoice_line_totals(lines):
    return {
        "quantity": round(sum(line["quantity"] for line in lines), 4),
        "total": round(sum(line["total"] for line in lines), 2),
        "cost_total": round(sum(line.get("cost_total", 0) for line in lines), 2),
        "tax_amount": round(sum(line["tax_amount"] for line in lines), 2),
        "withholding_amount": round(sum(line["withholding_amount"] for line in lines), 2),
        "grand_total": round(sum(line["grand_total"] for line in lines), 2),
    }


def _legacy_build_customer_statement_view(deps):
    db = deps["db"]
    get_company_settings = deps["get_company_settings"]

    def customer_statement(id):
        conn = db()
        cur = conn.cursor()
        company = get_company_settings(cur)
        cur.execute("SELECT name FROM customers WHERE id=?", (id,))
        customer = cur.fetchone()
        if not customer:
            conn.close()
            flash("ط§ظ„ط¹ظ…ظٹظ„ ط؛ظٹط± ظ…ظˆط¬ظˆط¯.", "danger")
            return redirect(url_for("customers"))

        entries = []

        cur.execute("SELECT date,id,grand_total,payment_type,status,cancel_reason FROM sales_invoices WHERE customer_id=? AND status<>'draft'", (id,))
        for date_value, invoice_id, total, payment_type, status, cancel_reason in cur.fetchall():
            display_status = "ظ…ظ„ط؛ظ‰" if status == "cancelled" else "ظ…ط±ط­ظ„"
            suffix = f" - ط³ط¨ط¨ ط§ظ„ط¥ظ„ط؛ط§ط،: {cancel_reason}" if status == "cancelled" and cancel_reason else ""
            if payment_type == "credit":
                entries.append((date_value, f"ظپط§طھظˆط±ط© ط¨ظٹط¹ ط¢ط¬ظ„ط© #{invoice_id}{suffix}", total, 0, display_status))
                if status == "cancelled":
                    entries.append((date_value, f"ط¥ظ„ط؛ط§ط، ظپط§طھظˆط±ط© ط¨ظٹط¹ ط¢ط¬ظ„ط© #{invoice_id}", 0, total, "ط¥ظ„ط؛ط§ط،"))
            else:
                entries.append((date_value, f"ظپط§طھظˆط±ط© ط¨ظٹط¹ ظ†ظ‚ط¯ظٹط© #{invoice_id}{suffix}", total, 0, display_status))
                entries.append((date_value, f"طھط­طµظٹظ„ ظ†ظ‚ط¯ظٹ ظ„ظپط§طھظˆط±ط© #{invoice_id}{suffix}", 0, total, display_status))

        cur.execute(
            """
            SELECT sr.date,sr.id,sr.grand_total,si.payment_type,p.name
            FROM sales_returns sr
            JOIN sales_invoices si ON si.id=sr.sales_invoice_id
            JOIN products p ON p.id=sr.product_id
            WHERE si.customer_id=?
            ORDER BY sr.id
            """,
            (id,),
        )
        for date_value, return_id, total, payment_type, product_name in cur.fetchall():
            if payment_type == "credit":
                entries.append((date_value, f"ظ…ط±ط¯ظˆط¯ ظ…ط¨ظٹط¹ط§طھ #{return_id} - {product_name}", 0, total, "ظ…ط±ط­ظ„"))
            else:
                entries.append((date_value, f"ظ…ط±ط¯ظˆط¯ ظ…ط¨ظٹط¹ط§طھ ظ†ظ‚ط¯ظٹ #{return_id} - {product_name}", 0, total, "ظ…ط±ط­ظ„"))
                entries.append((date_value, f"ط±ط¯ ظ†ظ‚ط¯ظٹط© ط¹ظ† ظ…ط±ط¯ظˆط¯ #{return_id}", total, 0, "ظ…ط±ط­ظ„"))

        cur.execute(
            """
            SELECT date,doc_no,adjustment_type,description,grand_total,status
            FROM customer_adjustments
            WHERE customer_id=? AND status<>'draft'
            ORDER BY id
            """,
            (id,),
        )
        for date_value, doc_no, adjustment_type, description, total, status in cur.fetchall():
            display_status = "ظ…ظ„ط؛ظ‰" if status == "cancelled" else "ظ…ط±ط­ظ„"
            if adjustment_type == "debit":
                entries.append((date_value, f"طھط³ظˆظٹط© ظ…ط¯ظٹظ†ط© {doc_no} - {description}", total, 0, display_status))
            else:
                entries.append((date_value, f"طھط³ظˆظٹط© ط¯ط§ط¦ظ†ط© {doc_no} - {description}", 0, total, display_status))

        cur.execute("SELECT date,id,amount,notes,status,cancel_reason FROM receipt_vouchers WHERE customer_id=? AND status<>'draft'", (id,))
        for date_value, voucher_id, amount, notes, status, cancel_reason in cur.fetchall():
            display_status = "ظ…ظ„ط؛ظ‰" if status == "cancelled" else "ظ…ط±ط­ظ„"
            label = f"ط³ظ†ط¯ ظ‚ط¨ط¶ #{voucher_id}"
            if notes:
                label += f" - {notes}"
            if status == "cancelled" and cancel_reason:
                label += f" - ط³ط¨ط¨ ط§ظ„ط¥ظ„ط؛ط§ط،: {cancel_reason}"
            entries.append((date_value, label, 0, amount, display_status))
            if status == "cancelled":
                entries.append((date_value, f"ط¥ظ„ط؛ط§ط، ط³ظ†ط¯ ظ‚ط¨ط¶ #{voucher_id}", amount, 0, "ط¥ظ„ط؛ط§ط،"))

        entries.sort(key=lambda row: (row[0], row[1]))
        debit = sum(row[2] for row in entries)
        credit = sum(row[3] for row in entries)
        balance = debit - credit
        conn.close()
        return render_template(
            "party_statement.html",
            title=f"ظƒط´ظپ ط­ط³ط§ط¨ ط§ظ„ط¹ظ…ظٹظ„: {customer[0]}",
            company=company,
            party_name=customer[0],
            party_type="ط¹ظ…ظٹظ„",
            rows=entries,
            debit=debit,
            credit=credit,
            balance=balance,
            balance_label="ظ…ط¯ظٹظ†" if balance > 0 else "ط¯ط§ط¦ظ†",
        )

    return customer_statement


def _legacy_build_supplier_statement_view(deps):
    db = deps["db"]
    get_company_settings = deps["get_company_settings"]

    def supplier_statement(id):
        conn = db()
        cur = conn.cursor()
        company = get_company_settings(cur)
        cur.execute("SELECT name FROM suppliers WHERE id=?", (id,))
        supplier = cur.fetchone()
        if not supplier:
            conn.close()
            flash("ط§ظ„ظ…ظˆط±ط¯ ط؛ظٹط± ظ…ظˆط¬ظˆط¯.", "danger")
            return redirect(url_for("suppliers"))
        entries = []
        cur.execute("SELECT date,id,grand_total,payment_type,status,cancel_reason FROM purchase_invoices WHERE supplier_id=? AND status<>'draft'", (id,))
        for date_value, invoice_id, total, payment_type, status, cancel_reason in cur.fetchall():
            display_status = "ظ…ظ„ط؛ظ‰" if status == "cancelled" else "ظ…ط±ط­ظ„"
            suffix = f" - ط³ط¨ط¨ ط§ظ„ط¥ظ„ط؛ط§ط،: {cancel_reason}" if status == "cancelled" and cancel_reason else ""
            if payment_type == "credit":
                entries.append((date_value, f"ظپط§طھظˆط±ط© ط´ط±ط§ط، ط¢ط¬ظ„ط© #{invoice_id}{suffix}", 0, total, display_status))
            else:
                entries.append((date_value, f"ظپط§طھظˆط±ط© ط´ط±ط§ط، ظ†ظ‚ط¯ظٹط© #{invoice_id}{suffix}", 0, total, display_status))
                entries.append((date_value, f"ط³ط¯ط§ط¯ ظ†ظ‚ط¯ظٹ ظ„ظپط§طھظˆط±ط© #{invoice_id}{suffix}", total, 0, display_status))
        cur.execute(
            """
            SELECT pr.date,pr.id,pr.grand_total,pi.payment_type,p.name
            FROM purchase_returns pr
            JOIN purchase_invoices pi ON pi.id=pr.purchase_invoice_id
            JOIN products p ON p.id=pr.product_id
            WHERE pi.supplier_id=?
            ORDER BY pr.id
            """,
            (id,),
        )
        for date_value, return_id, total, payment_type, product_name in cur.fetchall():
            if payment_type == "credit":
                entries.append((date_value, f"ظ…ط±ط¯ظˆط¯ ظ…ط´طھط±ظٹط§طھ #{return_id} - {product_name}", total, 0, "ظ…ط±ط­ظ„"))
            else:
                entries.append((date_value, f"ظ…ط±ط¯ظˆط¯ ظ…ط´طھط±ظٹط§طھ ظ†ظ‚ط¯ظٹ #{return_id} - {product_name}", total, 0, "ظ…ط±ط­ظ„"))
                entries.append((date_value, f"ط§ط³طھط±ط¯ط§ط¯ ظ†ظ‚ط¯ظٹط© ط¹ظ† ظ…ط±ط¯ظˆط¯ #{return_id}", 0, total, "ظ…ط±ط­ظ„"))
        cur.execute("SELECT date,id,amount,notes,status,cancel_reason FROM payment_vouchers WHERE supplier_id=? AND status<>'draft'", (id,))
        for date_value, voucher_id, amount, notes, status, cancel_reason in cur.fetchall():
            display_status = "ظ…ظ„ط؛ظ‰" if status == "cancelled" else "ظ…ط±ط­ظ„"
            label = f"ط³ظ†ط¯ طµط±ظپ #{voucher_id}"
            if notes:
                label += f" - {notes}"
            if status == "cancelled" and cancel_reason:
                label += f" - ط³ط¨ط¨ ط§ظ„ط¥ظ„ط؛ط§ط،: {cancel_reason}"
            entries.append((date_value, label, amount, 0, display_status))
            if status == "cancelled":
                entries.append((date_value, f"ط¥ظ„ط؛ط§ط، ط³ظ†ط¯ طµط±ظپ #{voucher_id}", 0, amount, "ط¥ظ„ط؛ط§ط،"))
        entries.sort(key=lambda row: row[0])
        debit = sum(row[2] for row in entries)
        credit = sum(row[3] for row in entries)
        balance = credit - debit
        conn.close()
        return render_template(
            "party_statement.html",
            title=f"ظƒط´ظپ ط­ط³ط§ط¨ ط§ظ„ظ…ظˆط±ط¯: {supplier[0]}",
            company=company,
            party_name=supplier[0],
            party_type="ظ…ظˆط±ط¯",
            rows=entries,
            debit=debit,
            credit=credit,
            balance=balance,
            balance_label="ط¯ط§ط¦ظ†" if balance > 0 else "ظ…ط¯ظٹظ†",
        )

    return supplier_statement


def _legacy_build_print_sale_view(deps):
    db = deps["db"]
    get_company_settings = deps["get_company_settings"]
    amount_to_words = deps["amount_to_words"]

    def print_sale(id):
        conn = db()
        cur = conn.cursor()
        company = get_company_settings(cur)
        cur.execute(
            """
            SELECT s.id,s.date,COALESCE(c.name,'ط¨ظٹط¹ ظ†ظ‚ط¯ظٹ'),COALESCE(c.phone,''),COALESCE(c.address,''),
                   p.name,p.unit,s.quantity,s.unit_price,s.total,s.tax_rate,s.tax_amount,s.grand_total,
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
            flash("ظپط§طھظˆط±ط© ط§ظ„ط¨ظٹط¹ ط؛ظٹط± ظ…ظˆط¬ظˆط¯ط©.", "danger")
            return redirect(url_for("sales"))
        return render_template(
            "print_document.html",
            company=company,
            doc=doc,
            doc_type="ظپط§طھظˆط±ط© ط¨ظٹط¹",
            party_label="ط§ظ„ط¹ظ…ظٹظ„",
            sales_invoice=True,
            amount_in_words=amount_to_words(doc[12]),
        )

    return print_sale


def build_sales_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]
    next_document_number = deps["next_document_number"]
    default_tax_rate = deps["DEFAULT_TAX_RATE"]
    is_group_posted = deps["is_group_posted"]

    def sales():
        conn = db()
        cur = conn.cursor()
        order_id = int(parse_positive_amount(request.values.get("sales_order_id")) or 0)
        prefilled_order = None
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            requested_invoice_number = (request.form.get("invoice_number") or "").strip()
            due_date = request.form.get("due_date", "").strip()
            customer_id = request.form.get("customer_id") or None
            payment_type = request.form.get("payment_type", "cash")
            po_ref = request.form.get("po_ref", "").strip()
            gr_ref = request.form.get("gr_ref", "").strip()
            notes = request.form.get("notes", "").strip()
            _, default_withholding_rate = _customer_withholding(cur, customer_id)
            vat_enabled, withholding_enabled, vat_rate, withholding_rate = _single_line_tax_selection(
                request.form,
                default_tax_rate,
                default_withholding_rate,
            )
            if order_id:
                existing_invoice = _existing_invoice_for_order(cur, "sales_invoices", "sales_order_id", order_id)
                if existing_invoice:
                    flash(f"تم تحويل أمر البيع مسبقًا إلى فاتورة {existing_invoice[1] or '#' + str(existing_invoice[0])}.", "warning")
                    conn.close()
                    return redirect(url_for("sales_invoices"))
                prefilled_order, lines = _sales_order_invoice_payload(cur, order_id, vat_rate, withholding_rate, withholding_enabled)
                if prefilled_order:
                    customer_id = prefilled_order["customer_id"] or customer_id
                    if not due_date:
                        due_date = prefilled_order["due_date"]
                    if not notes:
                        notes = prefilled_order["notes"]
            else:
                lines = _invoice_form_lines(cur, deps, "sale", vat_rate, withholding_rate, withholding_enabled)

            if not date_value:
                flash("التاريخ مطلوب.", "danger")
            elif payment_type == "credit" and not customer_id:
                flash("اختر العميل عند البيع الآجل.", "danger")
            elif not lines:
                flash("أضف صنفًا واحدًا على الأقل بكمية وسعر صحيحين.", "danger")
            elif vat_rate < 0 or withholding_rate < 0:
                flash("نسب الضرائب لا يمكن أن تكون سالبة.", "danger")
            elif not _has_enough_stock_for_lines(lines):
                flash("رصيد المخزون الحالي لا يكفي لإتمام الفاتورة.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("sales"))
                totals = _invoice_line_totals(lines)
                first_line = lines[0]
                debit_code = "1300" if payment_type == "credit" else "1100"
                group_posted = is_group_posted(cur, "sales")
                doc_no = requested_invoice_number or next_document_number(cur, "sales")
                if _invoice_number_exists(cur, "sales_invoices", doc_no):
                    conn.close()
                    flash("رقم الفاتورة مستخدم بالفعل", "danger")
                    return redirect(url_for("sales"))
                journal_id = None
                tax_journal_id = None
                withholding_journal_id = None
                cogs_journal_id = None

                if group_posted:
                    entry_specs = []
                    entry_roles = []
                    entry_specs.append({
                        "date": date_value,
                        "description": f"فاتورة بيع {doc_no}",
                        "debit_code": debit_code,
                        "credit_code": "4100",
                        "amount": totals["total"],
                        "source_type": "sales",
                    })
                    entry_roles.append("main")
                    if totals["tax_amount"] > 0:
                        entry_specs.append({
                            "date": date_value,
                            "description": f"ضريبة قيمة مضافة على فاتورة بيع {doc_no}",
                            "debit_code": debit_code,
                            "credit_code": "2200",
                            "amount": totals["tax_amount"],
                            "source_type": "sales",
                        })
                        entry_roles.append("tax")
                    if totals["withholding_amount"] > 0:
                        entry_specs.append({
                            "date": date_value,
                            "description": f"ضريبة خصم وإضافة عميل على فاتورة بيع {doc_no}",
                            "debit_code": "1510",
                            "credit_code": debit_code,
                            "amount": totals["withholding_amount"],
                            "source_type": "sales",
                        })
                        entry_roles.append("withholding")
                    if totals["cost_total"] > 0:
                        entry_specs.append({
                            "date": date_value,
                            "description": f"تكلفة بضاعة مباعة {doc_no}",
                            "debit_code": "6100",
                            "credit_code": "1400",
                            "amount": totals["cost_total"],
                            "source_type": "sales",
                        })
                        entry_roles.append("cogs")
                    posted_journal_ids = post_entries(cur, entry_specs, source_type="sales")
                    role_to_journal_id = dict(zip(entry_roles, posted_journal_ids))
                    journal_id = role_to_journal_id.get("main")
                    tax_journal_id = role_to_journal_id.get("tax")
                    withholding_journal_id = role_to_journal_id.get("withholding")
                    cogs_journal_id = role_to_journal_id.get("cogs")
                try:
                    cur.execute(
                        """
                        INSERT INTO sales_invoices(
                            date,due_date,doc_no,invoice_number,customer_id,product_id,quantity,unit_price,total,cost_total,
                            tax_rate,tax_amount,withholding_rate,withholding_amount,grand_total,payment_type,journal_id,tax_journal_id,withholding_journal_id,cogs_journal_id,status,
                            po_ref,gr_ref,notes,sales_order_id
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            date_value,
                            due_date,
                            doc_no,
                            doc_no,
                            customer_id,
                            first_line["product_id"],
                            totals["quantity"],
                            first_line["unit_price"],
                            totals["total"],
                            totals["cost_total"],
                            vat_rate,
                            totals["tax_amount"],
                            withholding_rate,
                            totals["withholding_amount"],
                            totals["grand_total"],
                            payment_type,
                            journal_id,
                            tax_journal_id,
                            withholding_journal_id,
                            cogs_journal_id,
                            "posted" if group_posted else "draft",
                            po_ref,
                            gr_ref,
                            notes,
                            order_id or None,
                        ),
                    )
                except sqlite3.IntegrityError:
                    conn.rollback()
                    flash("رقم الفاتورة مستخدم بالفعل", "danger")
                    conn.close()
                    return redirect(url_for("sales"))
                invoice_id = cur.lastrowid
                for line in lines:
                    cur.execute(
                        """
                        INSERT INTO sales_invoice_lines(
                            invoice_id,product_id,quantity,unit_price,total,cost_total,vat_enabled,withholding_enabled,vat_rate,withholding_rate,vat_amount,withholding_amount,grand_total,
                            unit_id,unit_name,conversion_factor,quantity_base,selected_unit,qty,base_qty
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            invoice_id,
                            line["product_id"],
                            line["quantity"],
                            line["unit_price"],
                            line["total"],
                            line["cost_total"],
                            1 if vat_enabled else 0,
                            1 if withholding_enabled else 0,
                            line["tax_rate"],
                            line["withholding_rate"],
                            line["tax_amount"],
                            line["withholding_amount"],
                            line["grand_total"],
                            line["unit_id"],
                            line["unit_name"],
                            line["conversion_factor"],
                            line["quantity_base"],
                            line["selected_unit"],
                            line["quantity"],
                            line["quantity_base"],
                        ),
                    )
                mark_journal_source(cur, "sales", invoice_id, journal_id, tax_journal_id, withholding_journal_id, cogs_journal_id)
                if group_posted:
                    for line in lines:
                        cur.execute("UPDATE products SET stock_quantity=stock_quantity-? WHERE id=?", (line["quantity_base"], line["product_id"]))
                        cur.execute(
                            """
                            INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes)
                            VALUES (?,?,?,?,?,?,?)
                            """,
                            (date_value, line["product_id"], "out", -line["quantity_base"], "sale", invoice_id, f"فاتورة بيع - {line['selected_unit']}"),
                        )
                log_action(cur, "create", "sales_invoice", invoice_id, f"{doc_no}; lines={len(lines)}; total={totals['grand_total']}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash("تم حفظ فاتورة البيع." + (" تم ترحيلها وتحديث المخزون." if group_posted else " محفوظة كمسودة غير مرحلة."), "success")
                return redirect(url_for("sales_invoices"))

        cur.execute("SELECT id,name FROM customers ORDER BY name")
        customers_rows = cur.fetchall()
        product_rows, product_units_map = _build_product_units_map(cur, "sale")
        initial_lines = [{}]
        if order_id:
            existing_invoice = _existing_invoice_for_order(cur, "sales_invoices", "sales_order_id", order_id)
            if existing_invoice:
                conn.close()
                flash(f"تم تحويل أمر البيع مسبقًا إلى فاتورة {existing_invoice[1] or '#' + str(existing_invoice[0])}.", "warning")
                return redirect(url_for("sales_invoices"))
            prefilled_order, order_lines = _sales_order_invoice_payload(cur, order_id, default_tax_rate, 0, False)
            if prefilled_order and order_lines:
                initial_lines = order_lines
        conn.close()
        return render_template(
            "sales_create.html",
            customers=customers_rows,
            products=product_rows,
            initial_lines=initial_lines,
            selected_customer_id=prefilled_order["customer_id"] if prefilled_order else None,
            selected_due_date=prefilled_order["due_date"] if prefilled_order else "",
            selected_notes=prefilled_order["notes"] if prefilled_order else "",
            sales_order_id=order_id or "",
            product_units_json=json.dumps(product_units_map, ensure_ascii=False),
        )

    return sales


def build_purchases_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]
    next_document_number = deps["next_document_number"]
    default_tax_rate = deps["DEFAULT_TAX_RATE"]
    is_group_posted = deps["is_group_posted"]

    def purchases():
        conn = db()
        cur = conn.cursor()
        order_id = int(parse_positive_amount(request.values.get("purchase_order_id")) or 0)
        prefilled_order = None
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            requested_invoice_number = (request.form.get("invoice_number") or "").strip()
            supplier_invoice_no = request.form.get("supplier_invoice_no", "").strip()
            supplier_invoice_date = request.form.get("supplier_invoice_date", "").strip()
            due_date = request.form.get("due_date", "").strip()
            notes = request.form.get("notes", "").strip()
            supplier_id = request.form.get("supplier_id") or None
            payment_type = request.form.get("payment_type", "cash")
            _, default_withholding_rate = _supplier_withholding(cur, supplier_id)
            vat_enabled, withholding_enabled, vat_rate, withholding_rate = _single_line_tax_selection(
                request.form,
                default_tax_rate,
                default_withholding_rate,
            )
            if order_id:
                existing_invoice = _existing_invoice_for_order(cur, "purchase_invoices", "purchase_order_id", order_id)
                if existing_invoice:
                    flash(f"تم تحويل أمر الشراء مسبقًا إلى فاتورة {existing_invoice[1] or '#' + str(existing_invoice[0])}.", "warning")
                    conn.close()
                    return redirect(url_for("purchase_invoices"))
                prefilled_order, lines = _purchase_order_invoice_payload(cur, order_id, vat_rate, withholding_rate, withholding_enabled)
                if prefilled_order:
                    supplier_id = prefilled_order["supplier_id"] or supplier_id
                    if not due_date:
                        due_date = prefilled_order["due_date"]
                    if not notes:
                        notes = prefilled_order["notes"]
            else:
                lines = _invoice_form_lines(cur, deps, "purchase", vat_rate, withholding_rate, withholding_enabled)

            if not date_value:
                flash("تاريخ التسجيل مطلوب.", "danger")
            elif not supplier_invoice_no:
                flash("رقم فاتورة المورد مطلوب.", "danger")
            elif not supplier_invoice_date:
                flash("تاريخ فاتورة المورد مطلوب.", "danger")
            elif payment_type == "credit" and not supplier_id:
                flash("اختر المورد عند الشراء الآجل.", "danger")
            elif not lines:
                flash("أضف صنفًا واحدًا على الأقل بكمية وسعر صحيحين.", "danger")
            elif vat_rate < 0 or withholding_rate < 0:
                flash("نسب الضرائب لا يمكن أن تكون سالبة.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("purchases"))
                totals = _invoice_line_totals(lines)
                first_line = lines[0]
                credit_code = "2100" if payment_type == "credit" else "1100"
                group_posted = is_group_posted(cur, "purchases")
                doc_no = requested_invoice_number or next_document_number(cur, "purchases")
                if _invoice_number_exists(cur, "purchase_invoices", doc_no):
                    conn.close()
                    flash("رقم الفاتورة مستخدم بالفعل", "danger")
                    return redirect(url_for("purchases"))
                journal_id = create_auto_journal(cur, date_value, f"فاتورة مورد {doc_no}", "1400", credit_code, totals["total"]) if group_posted else None
                tax_journal_id = None
                withholding_journal_id = None
                if group_posted and totals["tax_amount"] > 0:
                    tax_journal_id = create_auto_journal(
                        cur,
                        date_value,
                        f"ضريبة قيمة مضافة على فاتورة مورد {doc_no}",
                        "1500",
                        credit_code,
                        totals["tax_amount"],
                    )
                if group_posted and totals["withholding_amount"] > 0:
                    withholding_debit = "2100" if payment_type == "credit" else "1100"
                    withholding_journal_id = create_auto_journal(cur, date_value, f"ضريبة خصم وإضافة مورد على فاتورة مورد {doc_no}", withholding_debit, "2230", totals["withholding_amount"])
                try:
                    cur.execute(
                        """
                        INSERT INTO purchase_invoices(
                            date,doc_no,invoice_number,supplier_invoice_no,supplier_invoice_date,due_date,supplier_id,product_id,
                            quantity,unit_price,total,tax_rate,tax_amount,withholding_rate,withholding_amount,grand_total,payment_type,journal_id,tax_journal_id,withholding_journal_id,notes,status,purchase_order_id
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            date_value,
                            doc_no,
                            doc_no,
                            supplier_invoice_no,
                            supplier_invoice_date,
                            due_date,
                            supplier_id,
                            first_line["product_id"],
                            totals["quantity"],
                            first_line["unit_price"],
                            totals["total"],
                            vat_rate,
                            totals["tax_amount"],
                            withholding_rate,
                            totals["withholding_amount"],
                            totals["grand_total"],
                            payment_type,
                            journal_id,
                            tax_journal_id,
                            withholding_journal_id,
                            notes,
                            "posted" if group_posted else "draft",
                            order_id or None,
                        ),
                    )
                except sqlite3.IntegrityError:
                    conn.rollback()
                    flash("رقم الفاتورة مستخدم بالفعل", "danger")
                    conn.close()
                    return redirect(url_for("purchases"))
                invoice_id = cur.lastrowid
                for line in lines:
                    cur.execute(
                        """
                        INSERT INTO purchase_invoice_lines(
                            invoice_id,product_id,quantity,unit_price,total,vat_enabled,withholding_enabled,vat_rate,withholding_rate,vat_amount,withholding_amount,grand_total,
                            unit_id,unit_name,conversion_factor,quantity_base,selected_unit,qty,base_qty
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            invoice_id,
                            line["product_id"],
                            line["quantity"],
                            line["unit_price"],
                            line["total"],
                            1 if vat_enabled else 0,
                            1 if withholding_enabled else 0,
                            line["tax_rate"],
                            line["withholding_rate"],
                            line["tax_amount"],
                            line["withholding_amount"],
                            line["grand_total"],
                            line["unit_id"],
                            line["unit_name"],
                            line["conversion_factor"],
                            line["quantity_base"],
                            line["selected_unit"],
                            line["quantity"],
                            line["quantity_base"],
                        ),
                    )
                mark_journal_source(cur, "purchases", invoice_id, journal_id, tax_journal_id, withholding_journal_id)
                if group_posted:
                    for line in lines:
                        cur.execute("UPDATE products SET stock_quantity=stock_quantity+?, purchase_price=? WHERE id=?", (line["quantity_base"], line["unit_price"], line["product_id"]))
                        cur.execute(
                            """
                            INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes)
                            VALUES (?,?,?,?,?,?,?)
                            """,
                            (date_value, line["product_id"], "in", line["quantity_base"], "purchase", invoice_id, f"فاتورة شراء - {line['selected_unit']}"),
                        )
                log_action(cur, "create", "purchase_invoice", invoice_id, f"{doc_no}; lines={len(lines)}; total={totals['grand_total']}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash("تم حفظ فاتورة المورد." + (" تم ترحيلها وتحديث المخزون." if group_posted else " محفوظة كمسودة غير مرحلة."), "success")
                return redirect(url_for("purchase_invoices"))

        cur.execute("SELECT id,name FROM suppliers ORDER BY name")
        suppliers_rows = cur.fetchall()
        product_rows, product_units_map = _build_product_units_map(cur, "purchase")
        initial_lines = [{}]
        if order_id:
            existing_invoice = _existing_invoice_for_order(cur, "purchase_invoices", "purchase_order_id", order_id)
            if existing_invoice:
                conn.close()
                flash(f"تم تحويل أمر الشراء مسبقًا إلى فاتورة {existing_invoice[1] or '#' + str(existing_invoice[0])}.", "warning")
                return redirect(url_for("purchase_invoices"))
            prefilled_order, order_lines = _purchase_order_invoice_payload(cur, order_id, default_tax_rate, 0, False)
            if prefilled_order and order_lines:
                initial_lines = order_lines
        conn.close()
        return render_template(
            "purchases_create.html",
            suppliers=suppliers_rows,
            products=product_rows,
            initial_lines=initial_lines,
            selected_supplier_id=prefilled_order["supplier_id"] if prefilled_order else None,
            selected_due_date=prefilled_order["due_date"] if prefilled_order else "",
            selected_notes=prefilled_order["notes"] if prefilled_order else "",
            purchase_order_id=order_id or "",
            product_units_json=json.dumps(product_units_map, ensure_ascii=False),
        )

    return purchases


def build_sales_invoices_view(deps):
    db = deps["db"]

    def sales_invoices():
        from_date = (request.args.get("from_date") or "").strip()
        to_date = (request.args.get("to_date") or "").strip()
        conn = db()
        cur = conn.cursor()
        filters = []
        params = []
        if from_date:
            filters.append("s.date >= ?")
            params.append(from_date)
        if to_date:
            filters.append("s.date <= ?")
            params.append(to_date)
        where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
        cur.execute(
            f"""
            SELECT s.id,s.doc_no,s.date,COALESCE(c.name,'عميل نقدي'),s.grand_total,s.status,COALESCE(s.cancel_reason,''),
                   s.payment_type,COUNT(l.id),COALESCE(s.sales_order_id,0)
            FROM sales_invoices s
            LEFT JOIN customers c ON c.id=s.customer_id
            LEFT JOIN sales_invoice_lines l ON l.invoice_id=s.id
            {where_sql}
            GROUP BY s.id
            ORDER BY s.id DESC
            """,
            params,
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("sales_invoices.html", invoices=rows, from_date=from_date, to_date=to_date)

    return sales_invoices


def build_purchase_invoices_view(deps):
    db = deps["db"]

    def purchase_invoices():
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT p.id,p.doc_no,p.date,COALESCE(s.name,'شراء نقدي'),p.grand_total,p.status,COALESCE(p.cancel_reason,''),
                   p.payment_type,COUNT(l.id),COALESCE(p.purchase_order_id,0)
            FROM purchase_invoices p
            LEFT JOIN suppliers s ON s.id=p.supplier_id
            LEFT JOIN purchase_invoice_lines l ON l.invoice_id=p.id
            GROUP BY p.id
            ORDER BY p.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("purchase_invoices.html", invoices=rows)

    return purchase_invoices


def _legacy_build_receipts_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]
    is_group_posted = deps["is_group_posted"]

    def receipts():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            customer_id = request.form.get("customer_id")
            amount = parse_positive_amount(request.form.get("amount"))
            notes = request.form.get("notes", "").strip()

            cur.execute("SELECT name FROM customers WHERE id=?", (customer_id,))
            customer = cur.fetchone()

            if not date_value:
                flash("ط§ظ„طھط§ط±ظٹط® ظ…ط·ظ„ظˆط¨.", "danger")
            elif not customer:
                flash("ط§ظ„ط¹ظ…ظٹظ„ ط؛ظٹط± ظ…ظˆط¬ظˆط¯.", "danger")
            elif amount <= 0:
                flash("ط§ظ„ظ…ط¨ظ„ط؛ ظٹط¬ط¨ ط£ظ† ظٹظƒظˆظ† ط£ظƒط¨ط± ظ…ظ† طµظپط±.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("receipts"))
                group_posted = is_group_posted(cur, "receipts")
                journal_id = create_auto_journal(cur, date_value, f"ط³ظ†ط¯ ظ‚ط¨ط¶ ظ…ظ† {customer[0]}", "1100", "1300", amount) if group_posted else None
                cur.execute(
                    """
                    INSERT INTO receipt_vouchers(date,customer_id,amount,notes,journal_id,status)
                    VALUES (?,?,?,?,?,?)
                    """,
                    (date_value, customer_id, amount, notes, journal_id, "posted" if group_posted else "draft"),
                )
                voucher_id = cur.lastrowid
                mark_journal_source(cur, "receipts", voucher_id, journal_id)
                log_action(cur, "create", "receipt_voucher", voucher_id, f"amount={amount}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash("طھظ… ط­ظپط¸ ط³ظ†ط¯ ط§ظ„ظ‚ط¨ط¶." + (" طھظ… طھط±ط­ظٹظ„ظ‡." if group_posted else " ظ…ط­ظپظˆط¸ ظƒظ…ط³ظˆط¯ط© ط؛ظٹط± ظ…ط±ط­ظ„ط©."), "success")
                return redirect(url_for("receipts"))

        cur.execute("SELECT id,name FROM customers ORDER BY name")
        customers_rows = cur.fetchall()
        cur.execute(
            """
            SELECT r.id,r.date,c.name,r.amount,r.notes,r.status,r.cancel_reason
            FROM receipt_vouchers r
            JOIN customers c ON r.customer_id=c.id
            ORDER BY r.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("receipts.html", customers=customers_rows, rows=rows)

    return receipts


def _legacy_build_payments_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]
    is_group_posted = deps["is_group_posted"]

    def payments():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            supplier_id = request.form.get("supplier_id")
            amount = parse_positive_amount(request.form.get("amount"))
            notes = request.form.get("notes", "").strip()

            cur.execute("SELECT name FROM suppliers WHERE id=?", (supplier_id,))
            supplier = cur.fetchone()

            if not date_value:
                flash("ط§ظ„طھط§ط±ظٹط® ظ…ط·ظ„ظˆط¨.", "danger")
            elif not supplier:
                flash("ط§ظ„ظ…ظˆط±ط¯ ط؛ظٹط± ظ…ظˆط¬ظˆط¯.", "danger")
            elif amount <= 0:
                flash("ط§ظ„ظ…ط¨ظ„ط؛ ظٹط¬ط¨ ط£ظ† ظٹظƒظˆظ† ط£ظƒط¨ط± ظ…ظ† طµظپط±.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("payments"))
                group_posted = is_group_posted(cur, "payments")
                journal_id = create_auto_journal(cur, date_value, f"ط³ظ†ط¯ طµط±ظپ ط¥ظ„ظ‰ {supplier[0]}", "2100", "1100", amount) if group_posted else None
                cur.execute(
                    """
                    INSERT INTO payment_vouchers(date,supplier_id,amount,notes,journal_id,status)
                    VALUES (?,?,?,?,?,?)
                    """,
                    (date_value, supplier_id, amount, notes, journal_id, "posted" if group_posted else "draft"),
                )
                voucher_id = cur.lastrowid
                mark_journal_source(cur, "payments", voucher_id, journal_id)
                log_action(cur, "create", "payment_voucher", voucher_id, f"amount={amount}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash("طھظ… ط­ظپط¸ ط³ظ†ط¯ ط§ظ„طµط±ظپ." + (" طھظ… طھط±ط­ظٹظ„ظ‡." if group_posted else " ظ…ط­ظپظˆط¸ ظƒظ…ط³ظˆط¯ط© ط؛ظٹط± ظ…ط±ط­ظ„ط©."), "success")
                return redirect(url_for("payments"))

        cur.execute("SELECT id,name FROM suppliers ORDER BY name")
        suppliers_rows = cur.fetchall()
        cur.execute(
            """
            SELECT p.id,p.date,s.name,p.amount,p.notes,p.status,p.cancel_reason
            FROM payment_vouchers p
            JOIN suppliers s ON p.supplier_id=s.id
            ORDER BY p.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("payments.html", suppliers=suppliers_rows, rows=rows)

    return payments


def _legacy_build_print_receipt_view(deps):
    db = deps["db"]
    get_company_settings = deps["get_company_settings"]
    amount_to_words = deps["amount_to_words"]

    def print_receipt(id):
        conn = db()
        cur = conn.cursor()
        company = get_company_settings(cur)
        cur.execute(
            """
            SELECT r.id,r.date,c.name,COALESCE(c.phone,''),COALESCE(c.address,''),
                   r.amount,r.notes,r.status,r.cancel_reason
            FROM receipt_vouchers r
            JOIN customers c ON r.customer_id=c.id
            WHERE r.id=?
            """,
            (id,),
        )
        doc = cur.fetchone()
        conn.close()
        if not doc:
            flash("ط³ظ†ط¯ ط§ظ„ظ‚ط¨ط¶ ط؛ظٹط± ظ…ظˆط¬ظˆط¯.", "danger")
            return redirect(url_for("receipts"))
        return render_template(
            "print_voucher.html",
            company=company,
            doc=doc,
            doc_type="ط³ظ†ط¯ ظ‚ط¨ط¶",
            party_label="ط§ظ„ط¹ظ…ظٹظ„",
            amount_in_words=amount_to_words(doc[5]),
        )

    return print_receipt


def _legacy_build_print_payment_view(deps):
    db = deps["db"]
    get_company_settings = deps["get_company_settings"]
    amount_to_words = deps["amount_to_words"]

    def print_payment(id):
        conn = db()
        cur = conn.cursor()
        company = get_company_settings(cur)
        cur.execute(
            """
            SELECT p.id,p.date,s.name,COALESCE(s.phone,''),COALESCE(s.address,''),
                   p.amount,p.notes,p.status,p.cancel_reason
            FROM payment_vouchers p
            JOIN suppliers s ON p.supplier_id=s.id
            WHERE p.id=?
            """,
            (id,),
        )
        doc = cur.fetchone()
        conn.close()
        if not doc:
            flash("ط³ظ†ط¯ ط§ظ„طµط±ظپ ط؛ظٹط± ظ…ظˆط¬ظˆط¯.", "danger")
            return redirect(url_for("payments"))
        return render_template(
            "print_voucher.html",
            company=company,
            doc=doc,
            doc_type="ط³ظ†ط¯ طµط±ظپ",
            party_label="ط§ظ„ظ…ظˆط±ط¯",
            amount_in_words=amount_to_words(doc[5]),
        )

    return print_payment


def _legacy_build_customer_adjustments_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]
    next_document_number = deps["next_document_number"]
    is_group_posted = deps["is_group_posted"]

    def customer_adjustments():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            customer_id = int(parse_positive_amount(request.form.get("customer_id")) or 0)
            related_invoice_id = int(parse_positive_amount(request.form.get("related_invoice_id")) or 0) or None
            adjustment_type = request.form.get("adjustment_type", "").strip()
            description = request.form.get("description", "").strip()
            total = parse_positive_amount(request.form.get("total"))
            tax_rate = parse_positive_amount(request.form.get("tax_rate"))
            notes = request.form.get("notes", "").strip()
            tax_amount = total * tax_rate / 100
            grand_total = total + tax_amount
            cur.execute("SELECT name FROM customers WHERE id=?", (customer_id,))
            customer = cur.fetchone()
            if not date_value:
                flash("طھط§ط±ظٹط® ط§ظ„طھط³ظˆظٹط© ظ…ط·ظ„ظˆط¨.", "danger")
            elif adjustment_type not in ("debit", "credit"):
                flash("ظ†ظˆط¹ ط§ظ„طھط³ظˆظٹط© ط؛ظٹط± طµط­ظٹط­.", "danger")
            elif not customer:
                flash("ط§ظ„ط¹ظ…ظٹظ„ ط؛ظٹط± ظ…ظˆط¬ظˆط¯.", "danger")
            elif not description:
                flash("ظˆطµظپ ط§ظ„طھط³ظˆظٹط© ظ…ط·ظ„ظˆط¨.", "danger")
            elif total <= 0:
                flash("ظ…ط¨ظ„ط؛ ط§ظ„طھط³ظˆظٹط© ظٹط¬ط¨ ط£ظ† ظٹظƒظˆظ† ط£ظƒط¨ط± ظ…ظ† طµظپط±.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("customer_adjustments"))
                group_posted = is_group_posted(cur, "sales")
                journal_id = None
                tax_journal_id = None
                if group_posted:
                    if adjustment_type == "debit":
                        journal_id = create_auto_journal(cur, date_value, f"طھط³ظˆظٹط© ظ…ط¯ظٹظ†ط© ظ„ظ„ط¹ظ…ظٹظ„ {customer[0]} - {description}", "1300", "4400", total)
                        if tax_amount > 0:
                            tax_journal_id = create_auto_journal(cur, date_value, f"ط¶ط±ظٹط¨ط© طھط³ظˆظٹط© ظ…ط¯ظٹظ†ط© ظ„ظ„ط¹ظ…ظٹظ„ {customer[0]}", "1300", "2200", tax_amount)
                    else:
                        journal_id = create_auto_journal(cur, date_value, f"طھط³ظˆظٹط© ط¯ط§ط¦ظ†ط© ظ„ظ„ط¹ظ…ظٹظ„ {customer[0]} - {description}", "4200", "1300", total)
                        if tax_amount > 0:
                            tax_journal_id = create_auto_journal(cur, date_value, f"ط¶ط±ظٹط¨ط© طھط³ظˆظٹط© ط¯ط§ط¦ظ†ط© ظ„ظ„ط¹ظ…ظٹظ„ {customer[0]}", "2200", "1300", tax_amount)
                doc_no = next_document_number(cur, "customer_adjustments")
                cur.execute(
                    """
                    INSERT INTO customer_adjustments(
                        date,doc_no,customer_id,adjustment_type,related_invoice_id,description,total,tax_rate,tax_amount,grand_total,journal_id,tax_journal_id,status,notes
                    )
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        date_value,
                        doc_no,
                        customer_id,
                        adjustment_type,
                        related_invoice_id,
                        description,
                        total,
                        tax_rate,
                        tax_amount,
                        grand_total,
                        journal_id,
                        tax_journal_id,
                        "posted" if group_posted else "draft",
                        notes,
                    ),
                )
                adjustment_id = cur.lastrowid
                mark_journal_source(cur, "customer_adjustment", adjustment_id, journal_id, tax_journal_id)
                log_action(cur, "create", "customer_adjustment", adjustment_id, f"{doc_no}; type={adjustment_type}; total={grand_total}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash(f"طھظ… طھط³ط¬ظٹظ„ ط§ظ„طھط³ظˆظٹط© {doc_no}.", "success")
                return redirect(url_for("customer_adjustments"))

        cur.execute("SELECT id,name FROM customers ORDER BY name")
        customers_rows = cur.fetchall()
        cur.execute(
            """
            SELECT id,doc_no,date,grand_total
            FROM sales_invoices
            WHERE status='posted'
            ORDER BY id DESC
            """
        )
        invoices = cur.fetchall()
        cur.execute(
            """
            SELECT a.id,a.date,a.doc_no,c.name,a.adjustment_type,a.description,a.grand_total,a.status
            FROM customer_adjustments a
            JOIN customers c ON c.id=a.customer_id
            ORDER BY a.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("customer_adjustments.html", customers=customers_rows, invoices=invoices, rows=rows)

    return customer_adjustments


def _legacy_build_print_customer_adjustment_view(deps):
    db = deps["db"]
    get_company_settings = deps["get_company_settings"]
    amount_to_words = deps["amount_to_words"]

    def print_customer_adjustment(id):
        conn = db()
        cur = conn.cursor()
        company = get_company_settings(cur)
        cur.execute(
            """
            SELECT a.id,a.date,a.doc_no,c.name,COALESCE(c.phone,''),COALESCE(c.address,''),
                   a.description,a.total,a.tax_rate,a.tax_amount,a.grand_total,a.notes,a.adjustment_type,COALESCE(s.doc_no,'')
            FROM customer_adjustments a
            JOIN customers c ON c.id=a.customer_id
            LEFT JOIN sales_invoices s ON s.id=a.related_invoice_id
            WHERE a.id=?
            """,
            (id,),
        )
        doc = cur.fetchone()
        conn.close()
        if not doc:
            flash("ط§ظ„طھط³ظˆظٹط© ط؛ظٹط± ظ…ظˆط¬ظˆط¯ط©.", "danger")
            return redirect(url_for("customer_adjustments"))
        return render_template(
            "print_customer_note.html",
            company=company,
            doc=doc,
            doc_title="طھط³ظˆظٹط© ط¹ظ…ظٹظ„",
            note_kind=doc[12],
            amount_in_words=amount_to_words(doc[10]),
            source_label=f"ظ…ط±ط¬ط¹ ط§ظ„ظپط§طھظˆط±ط©: {doc[13]}" if doc[13] else "",
        )

    return print_customer_adjustment


def _legacy_build_prepare_customer_adjustment_einvoice_view(deps):
    db = deps["db"]
    prepare_einvoice_document = deps["prepare_einvoice_document"]
    log_action = deps["log_action"]

    def prepare_customer_adjustment_einvoice(id):
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT adjustment_type FROM customer_adjustments WHERE id=?", (id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            flash("ط§ظ„طھط³ظˆظٹط© ط؛ظٹط± ظ…ظˆط¬ظˆط¯ط©.", "danger")
            return redirect(url_for("customer_adjustments"))
        doc_type = "customer_debit_note" if row[0] == "debit" else "customer_credit_note"
        _, created = prepare_einvoice_document(cur, doc_type, id)
        log_action(cur, "prepare", "e_invoice_documents", None, f"{doc_type}={id}")
        conn.commit()
        conn.close()
        flash("طھظ… طھط¬ظ‡ظٹط² ط§ظ„طھط³ظˆظٹط© ظ„ظ„ط±ظپط¹ ط¹ظ„ظ‰ ط¨ظˆط±طھط§ظ„ ط§ظ„ط¶ط±ط§ط¦ط¨." if created else "ظ‡ط°ظ‡ ط§ظ„طھط³ظˆظٹط© ظ…ط¬ظ‡ط²ط© ط¨ط§ظ„ظپط¹ظ„ ظ„ظ„ط±ظپط¹.", "success")
        return redirect(url_for("customer_adjustments"))

    return prepare_customer_adjustment_einvoice


def _legacy_build_sales_orders_view(deps):
    db = deps["db"]
    parse_iso_date = deps["parse_iso_date"]
    log_action = deps["log_action"]

    def sales_orders():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            customer_id = request.form.get("customer_id") or None
            payment_terms = request.form.get("payment_terms", "").strip()
            delivery_date = request.form.get("delivery_date", "").strip()
            notes = request.form.get("notes", "").strip()
            lines = _order_lines_from_form(cur, deps)
            order_date = parse_iso_date(date_value)
            requested_delivery = parse_iso_date(delivery_date)
            if not date_value:
                flash("طھط§ط±ظٹط® ط£ظ…ط± ط§ظ„ط¨ظٹط¹ ظ…ط·ظ„ظˆط¨.", "danger")
            elif requested_delivery and order_date and requested_delivery < order_date:
                flash("طھط§ط±ظٹط® ط§ظ„طھط³ظ„ظٹظ… ظ„ط§ ظٹظ…ظƒظ† ط£ظ† ظٹظƒظˆظ† ط£ط³ط¨ظ‚ ظ…ظ† طھط§ط±ظٹط® ط£ظ…ط± ط§ظ„ط¨ظٹط¹.", "danger")
            elif not lines:
                flash("ط£ط¶ظپ طµظ†ظپط§ ظˆط§ط­ط¯ط§ ط¹ظ„ظ‰ ط§ظ„ط£ظ‚ظ„ ط¨ظƒظ…ظٹط© ظˆط³ط¹ط± طµط­ظٹط­ظٹظ†.", "danger")
            else:
                total = sum(line[3] for line in lines)
                tax_amount = sum(line[5] for line in lines)
                grand_total = sum(line[6] for line in lines)
                quantity = sum(line[1] for line in lines)
                first_line = lines[0]
                cur.execute(
                    """
                    INSERT INTO sales_orders(date,customer_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total,payment_terms,delivery_date,notes,status)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        date_value,
                        customer_id,
                        first_line[0],
                        quantity,
                        total / quantity if quantity else first_line[2],
                        total,
                        first_line[4],
                        tax_amount,
                        grand_total,
                        payment_terms,
                        delivery_date,
                        notes,
                        "issued",
                    ),
                )
                order_id = cur.lastrowid
                for line in lines:
                    cur.execute(
                        "INSERT INTO sales_order_lines(order_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total) VALUES (?,?,?,?,?,?,?,?)",
                        (order_id, *line),
                    )
                log_action(cur, "create", "sales_order", order_id, f"lines={len(lines)}; total={grand_total}")
                conn.commit()
                conn.close()
                flash("طھظ… ط­ظپط¸ ط£ظ…ط± ط§ظ„ط¨ظٹط¹ ظ…طھط¹ط¯ط¯ ط§ظ„ط£طµظ†ط§ظپ.", "success")
                return redirect(url_for("sales_orders"))

        cur.execute("SELECT id,name FROM customers ORDER BY name")
        customers_rows = cur.fetchall()
        cur.execute("SELECT id,name,sale_price,stock_quantity FROM products ORDER BY name")
        product_rows = cur.fetchall()
        cur.execute(
            """
            SELECT so.id,so.date,COALESCE(c.name,'ط¨ظٹط¹ ظ†ظ‚ط¯ظٹ'),COUNT(sol.id),so.quantity,so.grand_total,so.delivery_date,so.status
            FROM sales_orders so
            LEFT JOIN customers c ON c.id=so.customer_id
            LEFT JOIN sales_order_lines sol ON sol.order_id=so.id
            GROUP BY so.id
            ORDER BY so.id DESC
            """
        )
        base_rows = cur.fetchall()
        rows = []
        for row in base_rows:
            cur.execute(
                """
                SELECT p.name,sol.quantity
                FROM sales_order_lines sol
                JOIN products p ON p.id=sol.product_id
                WHERE sol.order_id=?
                ORDER BY sol.id
                """,
                (row[0],),
            )
            summary = " / ".join(f"{name} ({qty:g})" for name, qty in cur.fetchall())
            rows.append((row[0], row[1], row[2], summary, row[3], row[4], row[5], row[6], row[7]))
        conn.close()
        return render_template("sales_orders.html", customers=customers_rows, products=product_rows, rows=rows)

    return sales_orders


def _legacy_build_purchase_orders_view(deps):
    db = deps["db"]
    parse_iso_date = deps["parse_iso_date"]
    log_action = deps["log_action"]

    def purchase_orders():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            supplier_id = request.form.get("supplier_id")
            payment_terms = request.form.get("payment_terms", "").strip()
            delivery_date = request.form.get("delivery_date", "").strip()
            delivery_terms = request.form.get("delivery_terms", "").strip()
            notes = request.form.get("notes", "").strip()
            lines = _order_lines_from_form(cur, deps)
            order_date = parse_iso_date(date_value)
            requested_delivery = parse_iso_date(delivery_date)
            cur.execute("SELECT 1 FROM suppliers WHERE id=?", (supplier_id,))
            supplier = cur.fetchone()
            if not date_value:
                flash("طھط§ط±ظٹط® ط£ظ…ط± ط§ظ„ط´ط±ط§ط، ظ…ط·ظ„ظˆط¨.", "danger")
            elif not supplier:
                flash("ط§ط®طھط± ط§ظ„ظ…ظˆط±ط¯.", "danger")
            elif requested_delivery and order_date and requested_delivery < order_date:
                flash("طھط§ط±ظٹط® ط§ظ„طھظˆط±ظٹط¯ ظ„ط§ ظٹظ…ظƒظ† ط£ظ† ظٹظƒظˆظ† ط£ط³ط¨ظ‚ ظ…ظ† طھط§ط±ظٹط® ط£ظ…ط± ط§ظ„ط´ط±ط§ط،.", "danger")
            elif not lines:
                flash("ط£ط¶ظپ طµظ†ظپط§ ظˆط§ط­ط¯ط§ ط¹ظ„ظ‰ ط§ظ„ط£ظ‚ظ„ ط¨ظƒظ…ظٹط© ظˆط³ط¹ط± طµط­ظٹط­ظٹظ†.", "danger")
            else:
                total = sum(line[3] for line in lines)
                tax_amount = sum(line[5] for line in lines)
                grand_total = sum(line[6] for line in lines)
                quantity = sum(line[1] for line in lines)
                first_line = lines[0]
                cur.execute(
                    """
                    INSERT INTO purchase_orders(date,supplier_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total,payment_terms,delivery_date,delivery_terms,notes,status)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        date_value,
                        supplier_id,
                        first_line[0],
                        quantity,
                        total / quantity if quantity else first_line[2],
                        total,
                        first_line[4],
                        tax_amount,
                        grand_total,
                        payment_terms,
                        delivery_date,
                        delivery_terms,
                        notes,
                        "issued",
                    ),
                )
                order_id = cur.lastrowid
                for line in lines:
                    cur.execute(
                        "INSERT INTO purchase_order_lines(order_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total) VALUES (?,?,?,?,?,?,?,?)",
                        (order_id, *line),
                    )
                log_action(cur, "create", "purchase_order", order_id, f"lines={len(lines)}; total={grand_total}")
                conn.commit()
                conn.close()
                flash("طھظ… ط­ظپط¸ ط£ظ…ط± ط§ظ„ط´ط±ط§ط، ظ…طھط¹ط¯ط¯ ط§ظ„ط£طµظ†ط§ظپ.", "success")
                return redirect(url_for("purchase_orders"))

        cur.execute("SELECT id,name FROM suppliers ORDER BY name")
        suppliers_rows = cur.fetchall()
        cur.execute("SELECT id,name,purchase_price,stock_quantity FROM products ORDER BY name")
        product_rows = cur.fetchall()
        cur.execute(
            """
            SELECT po.id,po.date,s.name,COUNT(pol.id),po.quantity,po.grand_total,po.payment_terms,po.delivery_date,po.status
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id=s.id
            LEFT JOIN purchase_order_lines pol ON pol.order_id=po.id
            GROUP BY po.id
            ORDER BY po.id DESC
            """
        )
        base_rows = cur.fetchall()
        orders = []
        for row in base_rows:
            cur.execute(
                """
                SELECT p.name,pol.quantity
                FROM purchase_order_lines pol
                JOIN products p ON p.id=pol.product_id
                WHERE pol.order_id=?
                ORDER BY pol.id
                """,
                (row[0],),
            )
            summary = " / ".join(f"{name} ({qty:g})" for name, qty in cur.fetchall())
            orders.append((row[0], row[1], row[2], summary, row[3], row[4], row[5], row[6], row[7], row[8]))
        conn.close()
        return render_template("purchase_orders.html", suppliers=suppliers_rows, products=product_rows, orders=orders)

    return purchase_orders


def _legacy_build_print_purchase_order_view(deps):
    db = deps["db"]
    get_company_settings = deps["get_company_settings"]

    def print_purchase_order(id):
        conn = db()
        cur = conn.cursor()
        company = get_company_settings(cur)
        cur.execute(
            """
            SELECT po.id,po.date,s.name,COALESCE(s.phone,''),COALESCE(s.address,''),
                   po.payment_terms,po.delivery_date,po.delivery_terms,po.status,po.notes,
                   po.total,po.tax_amount,po.grand_total
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id=s.id
            WHERE po.id=?
            """,
            (id,),
        )
        order = cur.fetchone()
        cur.execute(
            """
            SELECT p.name,p.unit,pol.quantity,pol.unit_price,pol.total,pol.tax_amount,pol.grand_total
            FROM purchase_order_lines pol
            JOIN products p ON p.id=pol.product_id
            WHERE pol.order_id=?
            ORDER BY pol.id
            """,
            (id,),
        )
        lines = cur.fetchall()
        conn.close()
        if not order:
            flash("ط£ظ…ط± ط§ظ„ط´ط±ط§ط، ط؛ظٹط± ظ…ظˆط¬ظˆط¯.", "danger")
            return redirect(url_for("purchase_orders"))
        return render_template("print_purchase_order.html", company=company, order=order, lines=lines)

    return print_purchase_order


def _legacy_build_sales_deliveries_view(deps):
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
                SELECT so.id,sol.id,so.customer_id,sol.product_id,sol.quantity,sol.unit_price,sol.tax_rate,p.name,p.purchase_price,p.stock_quantity,so.date,so.delivery_date
                FROM sales_order_lines sol
                JOIN sales_orders so ON so.id=sol.order_id
                JOIN products p ON p.id=sol.product_id
                WHERE sol.id=?
                """,
                (line_id,),
            )
            order = cur.fetchone()
            cur.execute("SELECT COALESCE(SUM(delivered_quantity),0) FROM sales_delivery_notes WHERE sales_order_line_id=?", (line_id,))
            already_delivered = cur.fetchone()[0] if order else 0
            remaining = (order[4] - already_delivered) if order else 0
            movement_date = parse_iso_date(date_value)
            order_date = parse_iso_date(order[10]) if order else None
            planned_delivery_date = parse_iso_date(order[11]) if order else None
            if not date_value:
                flash("طھط§ط±ظٹط® ط¥ط°ظ† ط§ظ„طµط±ظپ ظ…ط·ظ„ظˆط¨.", "danger")
            elif not order:
                flash("ط¨ظ†ط¯ ط£ظ…ط± ط§ظ„ط¨ظٹط¹ ط؛ظٹط± ظ…ظˆط¬ظˆط¯.", "danger")
            elif movement_date and order_date and movement_date < order_date:
                flash("طھط§ط±ظٹط® ط¥ط°ظ† ط§ظ„طµط±ظپ ظ„ط§ ظٹظ…ظƒظ† ط£ظ† ظٹظƒظˆظ† ط£ط³ط¨ظ‚ ظ…ظ† طھط§ط±ظٹط® ط£ظ…ط± ط§ظ„ط¨ظٹط¹.", "danger")
            elif movement_date and planned_delivery_date and movement_date < planned_delivery_date:
                flash("طھط§ط±ظٹط® ط¥ط°ظ† ط§ظ„طµط±ظپ ظ„ط§ ظٹظ…ظƒظ† ط£ظ† ظٹظƒظˆظ† ط£ط³ط¨ظ‚ ظ…ظ† طھط§ط±ظٹط® ط§ظ„طھظˆط±ظٹط¯ ط§ظ„ظ…ط­ط¯ط¯ ظپظٹ ط£ظ…ط± ط§ظ„ط¨ظٹط¹.", "danger")
            elif delivered_quantity <= 0 or delivered_quantity > remaining:
                flash("ط§ظ„ظƒظ…ظٹط© ط§ظ„ظ…ظ†طµط±ظپط© ظٹط¬ط¨ ط£ظ† طھظƒظˆظ† ط£ظƒط¨ط± ظ…ظ† طµظپط± ظˆظ„ط§ طھطھط¬ط§ظˆط² ط§ظ„ظ…طھط¨ظ‚ظٹ.", "danger")
            elif delivered_quantity > order[9]:
                flash("ط±طµظٹط¯ ط§ظ„ظ…ط®ط²ظˆظ† ظ„ط§ ظٹظƒظپظٹ ظ„ط¥ط°ظ† ط§ظ„طµط±ظپ.", "danger")
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
                cogs_journal_id = create_auto_journal(cur, date_value, f"ط¥ط°ظ† طµط±ظپ ظ…ط¨ظٹط¹ط§طھ {delivery_no} - {order[7]}", "6100", "1400", cost_total) if cost_total > 0 else None
                cur.execute(
                    """
                    INSERT INTO sales_delivery_notes(delivery_no,date,sales_order_id,sales_order_line_id,customer_id,product_id,ordered_quantity,delivered_quantity,unit_price,total,cost_total,tax_rate,tax_amount,grand_total,cogs_journal_id,notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (delivery_no, date_value, order[0], order[1], order[2], order[3], order[4], delivered_quantity, order[5], total, cost_total, order[6], tax_amount, grand_total, cogs_journal_id, notes),
                )
                delivery_id = cur.lastrowid
                mark_journal_source(cur, "sales_delivery", delivery_id, cogs_journal_id)
                cur.execute("UPDATE products SET stock_quantity=stock_quantity-? WHERE id=?", (delivered_quantity, order[3]))
                cur.execute(
                    "INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes) VALUES (?,?,?,?,?,?,?)",
                    (date_value, order[3], "out", -delivered_quantity, "sales_delivery", delivery_id, f"ط¥ط°ظ† طµط±ظپ {delivery_no}"),
                )
                log_action(cur, "create", "sales_delivery", delivery_id, f"{delivery_no}; total={grand_total}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash(f"طھظ… طھط³ط¬ظٹظ„ ط¥ط°ظ† ط§ظ„طµط±ظپ {delivery_no}.", "success")
                return redirect(url_for("sales_deliveries"))

        cur.execute(
            """
            SELECT sol.id,so.id,so.date,COALESCE(c.name,'ط¨ظٹط¹ ظ†ظ‚ط¯ظٹ'),p.name,sol.quantity,sol.unit_price,
                   sol.quantity-COALESCE(SUM(sd.delivered_quantity),0) AS remaining
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
            SELECT sd.id,sd.delivery_no,sd.date,sd.sales_order_id,COALESCE(c.name,'ط¨ظٹط¹ ظ†ظ‚ط¯ظٹ'),p.name,
                   sd.delivered_quantity,sd.unit_price,sd.grand_total,sd.invoice_id
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


def _legacy_build_purchase_receipts_view(deps):
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
            cur.execute("SELECT COALESCE(SUM(received_quantity),0) FROM purchase_receipts WHERE purchase_order_line_id=?", (line_id,))
            already_received = cur.fetchone()[0] if order else 0
            remaining = (order[4] - already_received) if order else 0
            movement_date = parse_iso_date(date_value)
            order_date = parse_iso_date(order[8]) if order else None
            planned_supply_date = parse_iso_date(order[9]) if order else None
            if not date_value:
                flash("طھط§ط±ظٹط® ط¥ط°ظ† ط§ظ„ط§ط³طھظ„ط§ظ… ظ…ط·ظ„ظˆط¨.", "danger")
            elif not order:
                flash("ط¨ظ†ط¯ ط£ظ…ط± ط§ظ„ط´ط±ط§ط، ط؛ظٹط± ظ…ظˆط¬ظˆط¯.", "danger")
            elif movement_date and order_date and movement_date < order_date:
                flash("طھط§ط±ظٹط® ط¥ط°ظ† ط§ظ„ط§ط³طھظ„ط§ظ… ظ„ط§ ظٹظ…ظƒظ† ط£ظ† ظٹظƒظˆظ† ط£ط³ط¨ظ‚ ظ…ظ† طھط§ط±ظٹط® ط£ظ…ط± ط§ظ„ط´ط±ط§ط،.", "danger")
            elif movement_date and planned_supply_date and movement_date < planned_supply_date:
                flash("طھط§ط±ظٹط® ط¥ط°ظ† ط§ظ„ط§ط³طھظ„ط§ظ… ظ„ط§ ظٹظ…ظƒظ† ط£ظ† ظٹظƒظˆظ† ط£ط³ط¨ظ‚ ظ…ظ† طھط§ط±ظٹط® ط§ظ„طھظˆط±ظٹط¯ ط§ظ„ظ…ط­ط¯ط¯ ظپظٹ ط£ظ…ط± ط§ظ„ط´ط±ط§ط،.", "danger")
            elif received_quantity <= 0 or received_quantity > remaining:
                flash("ط§ظ„ظƒظ…ظٹط© ط§ظ„ظ…ط³طھظ„ظ…ط© ظٹط¬ط¨ ط£ظ† طھظƒظˆظ† ط£ظƒط¨ط± ظ…ظ† طµظپط± ظˆظ„ط§ طھطھط¬ط§ظˆط² ط§ظ„ظ…طھط¨ظ‚ظٹ.", "danger")
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
                journal_id = create_auto_journal(cur, date_value, f"ط¥ط°ظ† ط§ط³طھظ„ط§ظ… ظ…ط®ط²ظ†ظٹ {receipt_no} - {order[7]}", "1400", "2150", total)
                cur.execute(
                    """
                    INSERT INTO purchase_receipts(receipt_no,date,purchase_order_id,purchase_order_line_id,supplier_id,product_id,ordered_quantity,received_quantity,unit_price,total,tax_rate,tax_amount,grand_total,journal_id,notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (receipt_no, date_value, order[0], order[1], order[2], order[3], order[4], received_quantity, order[5], total, order[6], tax_amount, grand_total, journal_id, notes),
                )
                receipt_id = cur.lastrowid
                mark_journal_source(cur, "purchase_receipt", receipt_id, journal_id)
                cur.execute("UPDATE products SET stock_quantity=stock_quantity+?, purchase_price=? WHERE id=?", (received_quantity, order[5], order[3]))
                cur.execute(
                    "INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes) VALUES (?,?,?,?,?,?,?)",
                    (date_value, order[3], "in", received_quantity, "purchase_receipt", receipt_id, f"ط¥ط°ظ† ط§ط³طھظ„ط§ظ… {receipt_no}"),
                )
                log_action(cur, "create", "purchase_receipt", receipt_id, f"{receipt_no}; total={grand_total}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash(f"طھظ… طھط³ط¬ظٹظ„ ط¥ط°ظ† ط§ظ„ط§ط³طھظ„ط§ظ… {receipt_no}.", "success")
                return redirect(url_for("purchase_receipts"))

        cur.execute(
            """
            SELECT pol.id,po.id,po.date,s.name,p.name,pol.quantity,pol.unit_price,
                   pol.quantity-COALESCE(SUM(pr.received_quantity),0) AS remaining
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
                   pr.received_quantity,pr.unit_price,pr.grand_total,pr.invoice_id
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


def _legacy_build_sales_returns_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]
    default_tax_rate = deps["DEFAULT_TAX_RATE"]

    def sales_returns():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            invoice_id = int(parse_positive_amount(request.form.get("sales_invoice_id")) or 0)
            product_ids = request.form.getlist("product_id[]") or request.form.getlist("product_id")
            quantities = request.form.getlist("quantity[]") or request.form.getlist("quantity")
            po_ref = request.form.get("po_ref", "").strip()
            gr_ref = request.form.get("gr_ref", "").strip()
            notes = request.form.get("notes", "").strip()
            cur.execute("SELECT customer_id,payment_type,tax_rate FROM sales_invoices WHERE id=?", (invoice_id,))
            invoice = cur.fetchone()
            options_list = _invoice_product_options(cur, "sales", invoice_id)
            options = {item["product_id"]: item for item in options_list}
            lines = []
            for idx, product_id in enumerate(product_ids):
                product_id = int(parse_positive_amount(product_id) or 0)
                quantity = parse_positive_amount(quantities[idx] if idx < len(quantities) else 0)
                option = options.get(product_id)
                if product_id and quantity > 0 and option:
                    lines.append((product_id, quantity, option))
            if not date_value or not invoice or not lines:
                flash("ط±ط§ط¬ط¹ ط¨ظٹط§ظ†ط§طھ ظ…ط±ط¯ظˆط¯ ط§ظ„ط¨ظٹط¹.", "danger")
            elif any(line[1] > line[2]["available"] for line in lines):
                flash("ظٹظˆط¬ط¯ طµظ†ظپ طھطھط¬ط§ظˆط² ظƒظ…ظٹطھظ‡ ط§ظ„ظƒظ…ظٹط© ط§ظ„ظ…طھط§ط­ط© ظ„ظ„ظ…ط±ط¯ظˆط¯.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("sales_returns"))
                credit_code = "1300" if invoice[1] == "credit" else "1100"
                for product_id, quantity, option in lines:
                    total = quantity * option["unit_price"]
                    tax_amount = total * (invoice[2] or default_tax_rate) / 100
                    grand_total = total + tax_amount
                    cur.execute("SELECT name,purchase_price FROM products WHERE id=?", (product_id,))
                    product = cur.fetchone()
                    cost_total = quantity * (product[1] or 0)
                    journal_id = create_auto_journal(cur, date_value, f"ظ…ط±ط¯ظˆط¯ ط¨ظٹط¹ - {product[0]}", "4200", credit_code, total)
                    tax_journal_id = create_auto_journal(cur, date_value, f"ط¶ط±ظٹط¨ط© ظ…ط±ط¯ظˆط¯ ط¨ظٹط¹ - {product[0]}", "2200", credit_code, tax_amount) if tax_amount > 0 else None
                    cogs_journal_id = create_auto_journal(cur, date_value, f"ط¹ظƒط³ طھظƒظ„ظپط© ظ…ط±ط¯ظˆط¯ ط¨ظٹط¹ - {product[0]}", "1400", "6100", cost_total) if cost_total > 0 else None
                    cur.execute(
                        """
                        INSERT INTO sales_returns(date,sales_invoice_id,product_id,quantity,unit_price,total,tax_amount,grand_total,cost_total,journal_id,tax_journal_id,cogs_journal_id,po_ref,gr_ref,notes)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (date_value, invoice_id, product_id, quantity, option["unit_price"], total, tax_amount, grand_total, cost_total, journal_id, tax_journal_id, cogs_journal_id, po_ref, gr_ref, notes),
                    )
                    return_id = cur.lastrowid
                    mark_journal_source(cur, "sales_return", return_id, journal_id, tax_journal_id, cogs_journal_id)
                    cur.execute("UPDATE products SET stock_quantity=stock_quantity+? WHERE id=?", (quantity, product_id))
                    cur.execute(
                        "INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes) VALUES (?,?,?,?,?,?,?)",
                        (date_value, product_id, "return_in", quantity, "sales_return", return_id, notes or "ظ…ط±ط¯ظˆط¯ ط¨ظٹط¹"),
                    )
                    log_action(cur, "create", "sales_return", return_id, f"invoice={invoice_id}; total={grand_total}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash("طھظ… طھط³ط¬ظٹظ„ ظ…ط±ط¯ظˆط¯ط§طھ ط§ظ„ظ…ط¨ظٹط¹ط§طھ.", "success")
                return redirect(url_for("sales_returns"))
        cur.execute("SELECT id,date,grand_total FROM sales_invoices WHERE status='posted' ORDER BY id DESC")
        invoices = cur.fetchall()
        invoice_products = {}
        for row in invoices:
            invoice_products[row[0]] = _invoice_product_options(cur, "sales", row[0])
        cur.execute(
            """
            SELECT r.id,r.date,COALESCE(s.id,''),p.name,r.quantity,r.grand_total,r.status
            FROM sales_returns r
            LEFT JOIN sales_invoices s ON s.id=r.sales_invoice_id
            JOIN products p ON p.id=r.product_id
            ORDER BY r.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("returns.html", title="ظ…ط±ط¯ظˆط¯ط§طھ ط§ظ„ظ…ط¨ظٹط¹ط§طھ", rows=rows, invoices=invoices, invoice_products_json=json.dumps(invoice_products, ensure_ascii=False), action_url=url_for("sales_returns"), invoice_field="sales_invoice_id")

    return sales_returns


def _legacy_build_purchase_returns_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    ensure_open_period = deps["ensure_open_period"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]
    default_tax_rate = deps["DEFAULT_TAX_RATE"]

    def purchase_returns():
        conn = db()
        cur = conn.cursor()
        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            invoice_id = int(parse_positive_amount(request.form.get("purchase_invoice_id")) or 0)
            product_ids = request.form.getlist("product_id[]") or request.form.getlist("product_id")
            quantities = request.form.getlist("quantity[]") or request.form.getlist("quantity")
            po_ref = request.form.get("po_ref", "").strip()
            gr_ref = request.form.get("gr_ref", "").strip()
            notes = request.form.get("notes", "").strip()
            cur.execute("SELECT supplier_id,payment_type,tax_rate FROM purchase_invoices WHERE id=?", (invoice_id,))
            invoice = cur.fetchone()
            options_list = _invoice_product_options(cur, "purchase", invoice_id)
            options = {item["product_id"]: item for item in options_list}
            lines = []
            for idx, product_id in enumerate(product_ids):
                product_id = int(parse_positive_amount(product_id) or 0)
                quantity = parse_positive_amount(quantities[idx] if idx < len(quantities) else 0)
                option = options.get(product_id)
                if product_id and quantity > 0 and option:
                    lines.append((product_id, quantity, option))
            if not date_value or not invoice or not lines:
                flash("ط±ط§ط¬ط¹ ط¨ظٹط§ظ†ط§طھ ظ…ط±ط¯ظˆط¯ ط§ظ„ظ…ظˆط±ط¯.", "danger")
            else:
                for product_id, quantity, option in lines:
                    cur.execute("SELECT stock_quantity,name,purchase_price FROM products WHERE id=?", (product_id,))
                    product = cur.fetchone()
                    if not product or product[0] < quantity or quantity > option["available"]:
                        conn.close()
                        flash("ط±ط§ط¬ط¹ ط§ظ„ظƒظ…ظٹط§طھ ط§ظ„ظ…طھط§ط­ط© ظ„ظ„ظ…ط±ط¯ظˆط¯ ط£ظˆ ط±طµظٹط¯ ط§ظ„ظ…ط®ط²ظˆظ†.", "danger")
                        return redirect(url_for("purchase_returns"))
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("purchase_returns"))
                debit_code = "2100" if invoice[1] == "credit" else "1100"
                for product_id, quantity, option in lines:
                    cur.execute("SELECT name,purchase_price FROM products WHERE id=?", (product_id,))
                    product = cur.fetchone()
                    total = quantity * option["unit_price"]
                    tax_amount = total * (invoice[2] or default_tax_rate) / 100
                    grand_total = total + tax_amount
                    journal_id = create_auto_journal(cur, date_value, f"ظ…ط±ط¯ظˆط¯ ظ…ط´طھط±ظٹط§طھ - {product[0]}", debit_code, "1400", total)
                    tax_journal_id = create_auto_journal(cur, date_value, f"ط¶ط±ظٹط¨ط© ظ…ط±ط¯ظˆط¯ ظ…ط´طھط±ظٹط§طھ - {product[0]}", debit_code, "1500", tax_amount) if tax_amount > 0 else None
                    cur.execute(
                        """
                        INSERT INTO purchase_returns(date,purchase_invoice_id,supplier_id,product_id,quantity,unit_price,total,tax_amount,grand_total,journal_id,tax_journal_id,po_ref,gr_ref,notes)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (date_value, invoice_id, invoice[0], product_id, quantity, option["unit_price"], total, tax_amount, grand_total, journal_id, tax_journal_id, po_ref, gr_ref, notes),
                    )
                    return_id = cur.lastrowid
                    mark_journal_source(cur, "purchase_return", return_id, journal_id, tax_journal_id)
                    cur.execute("UPDATE products SET stock_quantity=stock_quantity-? WHERE id=?", (quantity, product_id))
                    cur.execute(
                        "INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes) VALUES (?,?,?,?,?,?,?)",
                        (date_value, product_id, "return_out", -quantity, "purchase_return", return_id, notes or "ظ…ط±ط¯ظˆط¯ ظ…ط´طھط±ظٹط§طھ"),
                    )
                    log_action(cur, "create", "purchase_return", return_id, f"invoice={invoice_id}; total={grand_total}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash("طھظ… طھط³ط¬ظٹظ„ ظ…ط±ط¯ظˆط¯ط§طھ ط§ظ„ظ…ظˆط±ط¯ظٹظ†.", "success")
                return redirect(url_for("purchase_returns"))
        cur.execute("SELECT id,date,grand_total FROM purchase_invoices WHERE status='posted' ORDER BY id DESC")
        invoices = cur.fetchall()
        invoice_products = {}
        for row in invoices:
            invoice_products[row[0]] = _invoice_product_options(cur, "purchase", row[0])
        cur.execute(
            """
            SELECT r.id,r.date,COALESCE(pu.id,''),p.name,r.quantity,r.grand_total,r.status
            FROM purchase_returns r
            LEFT JOIN purchase_invoices pu ON pu.id=r.purchase_invoice_id
            JOIN products p ON p.id=r.product_id
            ORDER BY r.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("returns.html", title="ظ…ط±ط¯ظˆط¯ط§طھ ط§ظ„ظ…ظˆط±ط¯ظٹظ†", rows=rows, invoices=invoices, invoice_products_json=json.dumps(invoice_products, ensure_ascii=False), action_url=url_for("purchase_returns"), invoice_field="purchase_invoice_id")

    return purchase_returns


def _legacy_build_sales_credit_notes_view(deps):
    db = deps["db"]
    ensure_open_period = deps["ensure_open_period"]
    next_document_number = deps["next_document_number"]
    log_action = deps["log_action"]

    def sales_credit_notes():
        conn = db()
        cur = conn.cursor()

        if request.method == "POST":
            date_value = request.form.get("date", "").strip()
            sales_return_id = int(deps["parse_positive_amount"](request.form.get("sales_return_id")) or 0)
            notes = request.form.get("notes", "").strip()
            cur.execute(
                """
                SELECT sr.id,sr.sales_invoice_id,si.customer_id,sr.product_id,sr.quantity,sr.unit_price,sr.total,sr.tax_amount,sr.grand_total
                FROM sales_returns sr
                JOIN sales_invoices si ON si.id=sr.sales_invoice_id
                WHERE sr.id=?
                """,
                (sales_return_id,),
            )
            sales_return = cur.fetchone()
            cur.execute("SELECT 1 FROM sales_credit_notes WHERE sales_return_id=?", (sales_return_id,))
            existing = cur.fetchone()
            if not date_value:
                flash("طھط§ط±ظٹط® ط§ظ„ظƒط±ظٹط¯طھ ظ†ظˆطھ ظ…ط·ظ„ظˆط¨.", "danger")
            elif not sales_return:
                flash("ظ…ط±ط¯ظˆط¯ ط§ظ„ظ…ط¨ظٹط¹ط§طھ ط§ظ„ظ…ط­ط¯ط¯ ط؛ظٹط± ظ…ظˆط¬ظˆط¯.", "danger")
            elif existing:
                flash("طھظ… ط¥طµط¯ط§ط± ظƒط±ظٹط¯طھ ظ†ظˆطھ ظ„ظ‡ط°ط§ ط§ظ„ظ…ط±ط¯ظˆط¯ ظ…ظ† ظ‚ط¨ظ„.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("sales_credit_notes"))
                doc_no = next_document_number(cur, "sales_credit_notes")
                cur.execute(
                    """
                    INSERT INTO sales_credit_notes(
                        date,doc_no,sales_return_id,sales_invoice_id,customer_id,product_id,quantity,unit_price,total,tax_amount,grand_total,notes,status
                    )
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        date_value,
                        doc_no,
                        sales_return[0],
                        sales_return[1],
                        sales_return[2],
                        sales_return[3],
                        sales_return[4],
                        sales_return[5],
                        sales_return[6],
                        sales_return[7],
                        sales_return[8],
                        notes,
                        "posted",
                    ),
                )
                note_id = cur.lastrowid
                log_action(cur, "create", "sales_credit_note", note_id, f"{doc_no}; return_id={sales_return_id}")
                conn.commit()
                conn.close()
                flash(f"طھظ… ط¥ظ†ط´ط§ط، ط§ظ„ظƒط±ظٹط¯طھ ظ†ظˆطھ {doc_no}.", "success")
                return redirect(url_for("sales_credit_notes"))

        cur.execute(
            """
            SELECT sr.id,sr.date,c.name,p.name,sr.grand_total
            FROM sales_returns sr
            JOIN sales_invoices si ON si.id=sr.sales_invoice_id
            LEFT JOIN customers c ON c.id=si.customer_id
            JOIN products p ON p.id=sr.product_id
            LEFT JOIN sales_credit_notes scn ON scn.sales_return_id=sr.id
            WHERE scn.id IS NULL
            ORDER BY sr.id DESC
            """
        )
        open_returns = cur.fetchall()
        cur.execute(
            """
            SELECT scn.id,scn.date,scn.doc_no,COALESCE(c.name,'ط¹ظ…ظٹظ„ ظ†ظ‚ط¯ظٹ'),p.name,scn.quantity,scn.grand_total,scn.sales_return_id
            FROM sales_credit_notes scn
            LEFT JOIN customers c ON c.id=scn.customer_id
            LEFT JOIN products p ON p.id=scn.product_id
            ORDER BY scn.id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("sales_credit_notes.html", open_returns=open_returns, rows=rows)

    return sales_credit_notes


def _legacy_build_print_purchase_view(deps):
    db = deps["db"]
    get_company_settings = deps["get_company_settings"]
    amount_to_words = deps["amount_to_words"]

    def print_purchase(id):
        conn = db()
        cur = conn.cursor()
        company = get_company_settings(cur)
        cur.execute(
            """
            SELECT p.id,p.date,COALESCE(s.name,'ط´ط±ط§ط، ظ†ظ‚ط¯ظٹ'),COALESCE(s.phone,''),COALESCE(s.address,''),
                   pr.name,pr.unit,p.quantity,p.unit_price,p.total,p.tax_rate,p.tax_amount,p.grand_total,
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
            flash("ظپط§طھظˆط±ط© ط§ظ„ط´ط±ط§ط، ط؛ظٹط± ظ…ظˆط¬ظˆط¯ط©.", "danger")
            return redirect(url_for("purchases"))
        return render_template(
            "print_document.html",
            company=company,
            doc=doc,
            doc_type="طھط³ط¬ظٹظ„ ظپط§طھظˆط±ط© ظ…ظˆط±ط¯",
            party_label="ط§ظ„ظ…ظˆط±ط¯",
            supplier_invoice=True,
            amount_in_words=amount_to_words(doc[12]),
        )

    return print_purchase


def _legacy_build_print_sales_credit_note_view(deps):
    db = deps["db"]
    get_company_settings = deps["get_company_settings"]
    amount_to_words = deps["amount_to_words"]

    def print_sales_credit_note(id):
        conn = db()
        cur = conn.cursor()
        company = get_company_settings(cur)
        cur.execute(
            """
            SELECT scn.id,scn.date,scn.doc_no,COALESCE(c.name,'ط¹ظ…ظٹظ„ ظ†ظ‚ط¯ظٹ'),COALESCE(c.phone,''),COALESCE(c.address,''),
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
            flash("ط§ظ„ظƒط±ظٹط¯طھ ظ†ظˆطھ ط؛ظٹط± ظ…ظˆط¬ظˆط¯.", "danger")
            return redirect(url_for("sales_credit_notes"))
        return render_template(
            "print_customer_note.html",
            company=company,
            doc=doc,
            doc_title="ظƒط±ظٹط¯طھ ظ†ظˆطھ ط¹ظ…ظٹظ„",
            note_kind="credit",
            amount_in_words=amount_to_words(doc[12]),
            source_label=f"ظ…ظ† ظˆط§ظ‚ط¹ ظ…ط±ط¯ظˆط¯ ط§ظ„ظ…ط¨ظٹط¹ط§طھ #{doc[14]} / ط§ظ„ظپط§طھظˆط±ط© ط§ظ„ط£طµظ„ظٹط© #{doc[15]}",
        )

    return print_sales_credit_note


def _legacy_build_prepare_sales_credit_note_einvoice_view(deps):
    db = deps["db"]
    prepare_einvoice_document = deps["prepare_einvoice_document"]
    log_action = deps["log_action"]

    def prepare_sales_credit_note_einvoice(id):
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM sales_credit_notes WHERE id=?", (id,))
        if not cur.fetchone():
            conn.close()
            flash("ط§ظ„ظƒط±ظٹط¯طھ ظ†ظˆطھ ط؛ظٹط± ظ…ظˆط¬ظˆط¯.", "danger")
            return redirect(url_for("sales_credit_notes"))
        _, created = prepare_einvoice_document(cur, "sales_credit_note", id)
        log_action(cur, "prepare", "e_invoice_documents", None, f"sales_credit_note={id}")
        conn.commit()
        conn.close()
        flash("طھظ… طھط¬ظ‡ظٹط² ط§ظ„ظƒط±ظٹط¯طھ ظ†ظˆطھ ظ„ظ„ط±ظپط¹ ط¹ظ„ظ‰ ط¨ظˆط±طھط§ظ„ ط§ظ„ط¶ط±ط§ط¦ط¨." if created else "ط§ظ„ظƒط±ظٹط¯طھ ظ†ظˆطھ ظ…ط¬ظ‡ط² ط¨ط§ظ„ظپط¹ظ„ ظ„ظ„ط±ظپط¹.", "success")
        return redirect(url_for("sales_credit_notes"))

    return prepare_sales_credit_note_einvoice


