import csv
import html
import io
import json
import os
import shutil
import sqlite3
from datetime import date, datetime
from functools import wraps

from flask import (
    Flask,
    Response,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from db import PERMISSION_MODULES, init_db
from modules.accounting.views import (
    build_account_delete_view,
    build_account_edit_view,
    build_accounts_view,
    build_delete_journal_view,
    build_edit_journal_view,
    build_journal_export_view,
    build_journal_view,
    build_ledger_export_view,
    build_ledger_view,
    build_trial_export_view,
    build_trial_view,
)
from modules.admin.views import (
    build_audit_log_view,
    build_backup_restore_view,
    build_permissions_view,
    build_users_view,
)
from modules.core.views import (
    build_company_settings_view,
    build_dashboard_view,
    build_fiscal_period_action_view,
    build_fiscal_periods_view,
    build_posting_control_action_view,
    build_posting_control_view,
)
from modules.einvoice.views import build_einvoices_view, build_prepare_sales_einvoices_view
from modules.hr.views import (
    build_delete_employee_view,
    build_edit_employee_view,
    build_employees_view,
    build_payroll_details_view,
    build_payroll_view,
    build_toggle_employee_view,
)
from modules.inventory.views import (
    build_delete_product_view,
    build_edit_product_view,
    build_inventory_report_view,
    build_inventory_view,
    build_product_barcode_view,
    build_products_view,
)
from modules.parties.views import (
    build_customers_view,
    build_party_delete_view,
    build_party_edit_view,
    build_suppliers_view,
)
from modules.reports.views import (
    build_customers_aging_report_view,
    build_customers_report_view,
    build_suppliers_aging_report_view,
    build_suppliers_report_view,
)
from modules.reports.financial import (
    build_balance_sheet_report_view,
    build_cash_flow_report_view,
    build_cost_center_report_view,
    build_opening_balances_view,
    build_profit_loss_report_view,
    build_vat_report_view,
    build_year_end_view,
)
from modules.sales.operations import (
    build_allocations_view,
    build_cancel_payment_view,
    build_cancel_purchase_view,
    build_cancel_receipt_view,
    build_cancel_sale_view,
    build_edit_payment_view,
    build_edit_purchase_invoice_view,
    build_edit_receipt_view,
    build_edit_sale_invoice_view,
)
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
    build_print_supplier_debit_note_view,
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
    build_supplier_debit_notes_view,
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
from modules.sales.views import (
    build_purchases_view,
    build_sales_view,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "erp-dev-secret")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
ACCOUNT_TYPES = ["أصول", "خصوم", "حقوق ملكية", "إيرادات", "مصروفات"]
DEFAULT_TAX_RATE = 14
LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg"}
MAX_LOGO_SIZE = 2 * 1024 * 1024

init_db()


def db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def get_company_settings(cur):
    cur.execute(
        """
        SELECT company_name,tax_number,commercial_register,address,phone,email,logo_path,default_tax_rate,invoice_footer
        FROM company_settings
        WHERE id=1
        """
    )
    row = cur.fetchone()
    if row:
        return {
            "company_name": row[0],
            "tax_number": row[1],
            "commercial_register": row[2],
            "address": row[3],
            "phone": row[4],
            "email": row[5],
            "logo_path": row[6],
            "default_tax_rate": row[7],
            "invoice_footer": row[8],
        }
    return {
        "company_name": "شركة تجارية افتراضية",
        "tax_number": "",
        "commercial_register": "",
        "address": "",
        "phone": "",
        "email": "",
        "logo_path": "",
        "default_tax_rate": DEFAULT_TAX_RATE,
        "invoice_footer": "",
    }


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if session.get("role") != "admin":
            flash("هذه الصفحة متاحة للمدير فقط.", "danger")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)

    return wrapped_view


ROLE_LABELS = {
    "admin": "مدير",
    "accountant": "محاسب",
    "sales": "مبيعات",
    "viewer": "مشاهدة فقط",
}

ROLE_PERMISSIONS = {
    "admin": {
        "accounting": "write",
        "customers": "write",
        "suppliers": "write",
        "inventory": "write",
        "sales": "write",
        "purchases": "write",
        "receipts": "write",
        "payments": "write",
        "hr": "write",
        "reports": "write",
        "e_invoices": "write",
    },
    "accountant": {
        "accounting": "write",
        "customers": "write",
        "suppliers": "write",
        "inventory": "write",
        "sales": "write",
        "purchases": "write",
        "receipts": "write",
        "payments": "write",
        "hr": "write",
        "reports": "read",
        "e_invoices": "write",
    },
    "sales": {
        "customers": "write",
        "inventory": "read",
        "sales": "write",
        "receipts": "write",
        "reports": "read",
    },
    "viewer": {
        "accounting": "read",
        "customers": "read",
        "suppliers": "read",
        "inventory": "read",
        "sales": "read",
        "purchases": "read",
        "receipts": "read",
        "payments": "read",
        "hr": "read",
        "reports": "read",
        "e_invoices": "read",
    },
}

POSTING_GROUPS = {
    "manual_journal": {
        "name": "القيود اليومية اليدوية",
        "table": "journal",
        "list_endpoint": "journal",
    },
    "sales": {
        "name": "فواتير البيع",
        "table": "sales_invoices",
        "list_endpoint": "sales",
    },
    "purchases": {
        "name": "فواتير الموردين",
        "table": "purchase_invoices",
        "list_endpoint": "purchases",
    },
    "receipts": {
        "name": "سندات القبض",
        "table": "receipt_vouchers",
        "list_endpoint": "receipts",
    },
    "payments": {
        "name": "سندات الصرف",
        "table": "payment_vouchers",
        "list_endpoint": "payments",
    },
}


def permission_level(permission):
    role = session.get("role", "viewer")
    if role == "admin":
        return "write"
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute(
            "SELECT access_level FROM role_permissions WHERE role=? AND permission_key=?",
            (role, permission),
        )
        row = cur.fetchone()
        conn.close()
        if row:
            return row[0]
    except sqlite3.Error:
        pass
    return ROLE_PERMISSIONS.get(role, {}).get(permission, "none")


def has_permission(permission, write=False):
    level = permission_level(permission)
    if write:
        return level == "write"
    return level in ("read", "write")


def permission_required(permission, write_always=False):
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            write_request = write_always or request.method not in ("GET", "HEAD", "OPTIONS")
            if not has_permission(permission, write=write_request):
                flash("ليس لديك الصلاحية اللازمة لتنفيذ هذه العملية.", "danger")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)

        return wrapped_view

    return decorator


@app.context_processor
def inject_permissions():
    settings = {}
    try:
        conn = db()
        cur = conn.cursor()
        settings = get_company_settings(cur)
        conn.close()
    except sqlite3.Error:
        settings = {}
    return {
        "can_read": lambda permission: has_permission(permission),
        "can_write": lambda permission: has_permission(permission, write=True),
        "role_label": ROLE_LABELS.get(session.get("role", "viewer"), session.get("role", "")),
        "company_settings": settings,
    }


def csv_response(filename, headers, rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(headers)
    writer.writerows(rows)
    data = "\ufeff" + stream.getvalue()
    return Response(
        data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def excel_response(filename, headers, rows, title="طھظ‚ط±ظٹط±"):
    def _cell(value):
        return "" if value is None else html.escape(str(value))

    header_html = "".join(f"<th>{_cell(item)}</th>" for item in headers)
    body_html = []
    for row in rows:
        body_html.append("<tr>" + "".join(f"<td>{_cell(item)}</td>" for item in row) + "</tr>")
    document = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<style>
body {{ font-family: Tahoma, Arial, sans-serif; direction: rtl; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #d0d7de; padding: 6px 8px; text-align: right; }}
th {{ background: #f6f8fa; font-weight: 700; }}
</style>
</head>
<body>
<h2>{_cell(title)}</h2>
<table>
<thead><tr>{header_html}</tr></thead>
<tbody>{''.join(body_html)}</tbody>
</table>
</body>
</html>"""
    return Response(
        "\ufeff" + document,
        mimetype="application/vnd.ms-excel; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def account_exists(cur, account_id):
    cur.execute("SELECT 1 FROM accounts WHERE id=?", (account_id,))
    return cur.fetchone() is not None


def validate_account_form(cur, form, current_id=None):
    errors = []
    code = form.get("code", "").strip()
    name = form.get("name", "").strip()
    account_type = form.get("type", "").strip()

    if not code:
        errors.append("كود الحساب مطلوب.")
    if not name:
        errors.append("اسم الحساب مطلوب.")
    if account_type not in ACCOUNT_TYPES:
        errors.append("نوع الحساب غير صحيح.")

    if code:
        cur.execute("SELECT id FROM accounts WHERE code=?", (code,))
        existing = cur.fetchone()
        if existing and existing[0] != current_id:
            errors.append("كود الحساب مستخدم بالفعل.")

    return errors, {"code": code, "name": name, "type": account_type}


def validate_journal_form(cur, form):
    errors = []

    date = form.get("date", "").strip()
    description = form.get("description", "").strip()
    debit = form.get("debit", "").strip()
    credit = form.get("credit", "").strip()
    amount_raw = form.get("amount", "").strip()
    cost_center_id = form.get("cost_center_id") or None

    try:
        amount = float(amount_raw)
    except ValueError:
        amount = 0
        errors.append("المبلغ يجب أن يكون رقمًا صحيحًا.")

    if not date:
        errors.append("التاريخ مطلوب.")
    if not description:
        errors.append("البيان مطلوب.")
    if not debit or not credit:
        errors.append("يجب اختيار الحساب المدين والحساب الدائن.")
    if debit and credit and debit == credit:
        errors.append("لا يمكن أن يكون الحساب المدين هو نفسه الحساب الدائن.")
    if amount <= 0:
        errors.append("المبلغ يجب أن يكون أكبر من صفر.")

    if debit and not account_exists(cur, debit):
        errors.append("الحساب المدين غير موجود.")
    if credit and not account_exists(cur, credit):
        errors.append("الحساب الدائن غير موجود.")
    if cost_center_id:
        cur.execute("SELECT id FROM cost_centers WHERE id=? AND status='active'", (cost_center_id,))
        if not cur.fetchone():
            errors.append("مركز التكلفة غير موجود أو غير نشط.")

    return errors, {
        "date": date,
        "description": description,
        "debit": debit,
        "credit": credit,
        "amount": amount,
        "cost_center_id": cost_center_id,
    }


def rebuild_ledger():
    conn = db()
    cur = conn.cursor()

    cur.execute("DELETE FROM ledger")
    cur.execute(
        """
        SELECT id,date,description,debit_account_id,credit_account_id,amount
        FROM journal
        WHERE status='posted'
        ORDER BY id
        """
    )
    rows = cur.fetchall()

    for r in rows:
        jid, date, desc, debit, credit, amount = r

        cur.execute(
            """
            INSERT INTO ledger(account_id,date,description,debit,credit,journal_id)
            VALUES (?,?,?,?,?,?)
            """,
            (debit, date, desc, amount, 0, jid),
        )

        cur.execute(
            """
            INSERT INTO ledger(account_id,date,description,debit,credit,journal_id)
            VALUES (?,?,?,?,?,?)
            """,
            (credit, date, desc, 0, amount, jid),
        )

    conn.commit()
    conn.close()


@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT id, username, password, role FROM users WHERE username=?", (username,))
        user = cur.fetchone()

        valid_password = False
        if user:
            stored_password = user[2]
            if stored_password.startswith("scrypt:") or stored_password.startswith("pbkdf2:"):
                valid_password = check_password_hash(stored_password, password)
            else:
                valid_password = stored_password == password
                if valid_password:
                    cur.execute(
                        "UPDATE users SET password=? WHERE id=?",
                        (generate_password_hash(password), user[0]),
                    )
                    conn.commit()

        conn.close()

        if valid_password:
            session.clear()
            session["user_id"] = user[0]
            session["username"] = user[1]
            session["role"] = user[3]
            return redirect(url_for("dashboard"))

        flash("اسم المستخدم أو كلمة المرور غير صحيحة.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    return build_dashboard_view(MODULE_DEPS)()


@app.route("/settings/company", methods=["GET", "POST"])
@login_required
@admin_required
def company_settings():
    return build_company_settings_view(MODULE_DEPS)()
@app.route("/posting-control")
@login_required
@admin_required
def posting_control():
    return build_posting_control_view(MODULE_DEPS)()
@app.route("/posting-control/<group_key>/<action>", methods=["POST"])
@login_required
@admin_required
def posting_control_action(group_key, action):
    return build_posting_control_action_view(MODULE_DEPS)(group_key, action)
@app.route("/fiscal-periods", methods=["GET", "POST"])
@login_required
@admin_required
def fiscal_periods():
    return build_fiscal_periods_view(MODULE_DEPS)()
@app.route("/fiscal-periods/<int:id>/<action>", methods=["POST"])
@login_required
@admin_required
def fiscal_period_action(id, action):
    return build_fiscal_period_action_view(MODULE_DEPS)(id, action)
@app.route("/accounts", methods=["GET", "POST"])
@login_required
@permission_required("accounting")
def accounts():
    return build_accounts_view(MODULE_DEPS)()


@app.route("/accounts/edit/<int:id>", methods=["GET", "POST"])
@login_required
@permission_required("accounting", write_always=True)
def account_edit(id):
    return build_account_edit_view(MODULE_DEPS)(id)


@app.route("/accounts/delete/<int:id>", methods=["POST"])
@login_required
@permission_required("accounting", write_always=True)
def account_delete(id):
    return build_account_delete_view(MODULE_DEPS)(id)


@app.route("/journal", methods=["GET", "POST"])
@login_required
@permission_required("accounting")
def journal():
    return build_journal_view(MODULE_DEPS)()


@app.route("/journal/export")
@login_required
@permission_required("accounting")
def journal_export():
    return build_journal_export_view(MODULE_DEPS)()


@app.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
@permission_required("accounting", write_always=True)
def edit(id):
    return build_edit_journal_view(MODULE_DEPS)(id)


@app.route("/delete/<int:id>", methods=["POST"])
@login_required
@permission_required("accounting", write_always=True)
def delete(id):
    return build_delete_journal_view(MODULE_DEPS)(id)


@app.route("/ledger/<int:id>")
@login_required
@permission_required("accounting")
def ledger(id):
    return build_ledger_view(MODULE_DEPS)(id)


@app.route("/ledger/<int:id>/export")
@login_required
@permission_required("accounting")
def ledger_export(id):
    return build_ledger_export_view(MODULE_DEPS)(id)


@app.route("/trial-balance")
@login_required
@permission_required("accounting")
def trial():
    return build_trial_view(MODULE_DEPS)()


@app.route("/trial-balance/export")
@login_required
@permission_required("accounting")
def trial_export():
    return build_trial_export_view(MODULE_DEPS)()


def get_account_id(cur, code):
    cur.execute("SELECT id FROM accounts WHERE code=?", (code,))
    row = cur.fetchone()
    return row[0] if row else None


def create_auto_journal(cur, date, description, debit_code, credit_code, amount):
    debit_id = get_account_id(cur, debit_code)
    credit_id = get_account_id(cur, credit_code)
    if not debit_id or not credit_id:
        raise ValueError("الحسابات الافتراضية غير مكتملة. راجع دليل الحسابات أولًا.")

    cur.execute(
        """
        INSERT INTO journal(date,description,debit_account_id,credit_account_id,amount,status,source_type)
        VALUES (?,?,?,?,?,'posted','auto')
        """,
        (date, description, debit_id, credit_id, amount),
    )
    return cur.lastrowid


def mark_journal_source(cur, source_type, source_id, *journal_ids):
    ids = [jid for jid in journal_ids if jid]
    if not ids:
        return
    placeholders = ",".join(["?"] * len(ids))
    cur.execute(
        f"UPDATE journal SET source_type=?, source_id=? WHERE id IN ({placeholders})",
        (source_type, source_id, *ids),
    )


def delete_journal_rows(cur, *journal_ids):
    ids = [jid for jid in journal_ids if jid]
    if not ids:
        return
    placeholders = ",".join(["?"] * len(ids))
    cur.execute(f"DELETE FROM journal WHERE id IN ({placeholders})", ids)


def ensure_posting_rows(cur):
    for group_key, info in POSTING_GROUPS.items():
        cur.execute("SELECT group_key FROM posting_control WHERE group_key=?", (group_key,))
        if cur.fetchone():
            cur.execute("UPDATE posting_control SET group_name=? WHERE group_key=?", (info["name"], group_key))
        else:
            cur.execute(
                "INSERT INTO posting_control(group_key,group_name,is_posted,posted_at,posted_by) VALUES (?,?,1,CURRENT_TIMESTAMP,?)",
                (group_key, info["name"], session.get("username", "system")),
            )


def is_group_posted(cur, group_key):
    ensure_posting_rows(cur)
    cur.execute("SELECT is_posted FROM posting_control WHERE group_key=?", (group_key,))
    row = cur.fetchone()
    return bool(row and row[0])


def status_label(status):
    if status == "posted":
        return "مرحل"
    if status == "draft":
        return "غير مرحل"
    if status == "cancelled":
        return "ملغى"
    return status or ""


def next_document_number(cur, doc_type):
    document_tables = {
        "sales": ("sales_invoices", "doc_no"),
        "purchases": ("purchase_invoices", "doc_no"),
        "sales_delivery_notes": ("sales_delivery_notes", "delivery_no"),
        "financial_sales": ("financial_sales_invoices", "doc_no"),
        "purchase_receipts": ("purchase_receipts", "receipt_no"),
        "sales_credit_notes": ("sales_credit_notes", "doc_no"),
        "supplier_debit_notes": ("supplier_debit_notes", "doc_no"),
        "customer_adjustments": ("customer_adjustments", "doc_no"),
    }
    cur.execute("SELECT prefix,next_number FROM document_sequences WHERE doc_type=?", (doc_type,))
    row = cur.fetchone()
    if not row:
        prefix = doc_type.upper()[:3]
        cur.execute(
            "INSERT INTO document_sequences(doc_type,prefix,next_number) VALUES (?,?,1)",
            (doc_type, prefix),
        )
        next_number = 1
    else:
        prefix, next_number = row
    table_info = document_tables.get(doc_type)
    while True:
        doc_no = f"{prefix}-{next_number:06d}"
        exists = False
        if table_info:
            table_name, column_name = table_info
            cur.execute(f"SELECT 1 FROM {table_name} WHERE {column_name}=? LIMIT 1", (doc_no,))
            exists = bool(cur.fetchone())
        if not exists:
            cur.execute("UPDATE document_sequences SET next_number=? WHERE doc_type=?", (next_number + 1, doc_type))
            return doc_no
        next_number += 1


def get_form_lines(cur):
    product_ids = request.form.getlist("product_id")
    quantities = request.form.getlist("quantity")
    unit_prices = request.form.getlist("unit_price")
    lines = []
    for product_id, quantity_raw, price_raw in zip(product_ids, quantities, unit_prices):
        if not product_id:
            continue
        quantity = parse_positive_amount(quantity_raw)
        unit_price = parse_positive_amount(price_raw)
        if quantity <= 0 or unit_price <= 0:
            continue
        cur.execute("SELECT name,stock_quantity,purchase_price FROM products WHERE id=?", (product_id,))
        product = cur.fetchone()
        if not product:
            continue
        total = quantity * unit_price
        cost_total = quantity * (product[2] or 0)
        lines.append(
            {
                "product_id": int(product_id),
                "name": product[0],
                "stock_quantity": product[1] or 0,
                "purchase_price": product[2] or 0,
                "quantity": quantity,
                "unit_price": unit_price,
                "total": total,
                "cost_total": cost_total,
            }
        )
    return lines


def post_sales_invoice(cur, invoice_id):
    cur.execute(
        """
        SELECT date,product_id,quantity,unit_price,total,cost_total,tax_amount,withholding_amount,payment_type,status
        FROM sales_invoices
        WHERE id=?
        """,
        (invoice_id,),
    )
    row = cur.fetchone()
    if not row or row[9] != "draft":
        return
    date_value, product_id, quantity, unit_price, total, cost_total, tax_amount, withholding_amount, payment_type, _ = row
    cur.execute("SELECT name, stock_quantity FROM products WHERE id=?", (product_id,))
    product = cur.fetchone()
    if not product or product[1] < quantity:
        raise ValueError(f"ط·آ·ط¢آ±ط·آ·ط¢آµط·آ¸ط¸آ¹ط·آ·ط¢آ¯ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آµط·آ¸أ¢â‚¬آ ط·آ¸ط¸آ¾ ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ ط·آ¸ط¸آ¹ط·آ¸ط¦â€™ط·آ¸ط¸آ¾ط·آ¸ط¸آ¹ ط·آ¸أ¢â‚¬â€چط·آ·ط¹آ¾ط·آ·ط¢آ±ط·آ·ط¢آ­ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ #{invoice_id}.")
    debit_code = "1300" if payment_type == "credit" else "1100"
    journal_id = create_auto_journal(cur, date_value, f"ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ - {product[0]}", debit_code, "4100", total)
    tax_journal_id = create_auto_journal(cur, date_value, f"ط·آ·ط¢آ¶ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ¨ط·آ·ط¢آ© ط·آ¸أ¢â‚¬ع‘ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ© ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ¶ط·آ·ط¢آ§ط·آ¸ط¸آ¾ط·آ·ط¢آ© ط·آ·ط¢آ¹ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ° ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ - {product[0]}", debit_code, "2200", tax_amount) if tax_amount > 0 else None
    withholding_journal_id = create_auto_journal(cur, date_value, f"ضريبة خصم وإضافة عميل على فاتورة بيع - {product[0]}", "1510", debit_code, withholding_amount) if withholding_amount > 0 else None
    cogs_journal_id = create_auto_journal(cur, date_value, f"ط·آ·ط¹آ¾ط·آ¸ط¦â€™ط·آ¸أ¢â‚¬â€چط·آ¸ط¸آ¾ط·آ·ط¢آ© ط·آ·ط¢آ¨ط·آ·ط¢آ¶ط·آ·ط¢آ§ط·آ·ط¢آ¹ط·آ·ط¢آ© ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ¨ط·آ·ط¢آ§ط·آ·ط¢آ¹ط·آ·ط¢آ© - {product[0]}", "6100", "1400", cost_total) if cost_total > 0 else None
    mark_journal_source(cur, "sales", invoice_id, journal_id, tax_journal_id, withholding_journal_id, cogs_journal_id)
    cur.execute("UPDATE products SET stock_quantity=stock_quantity-? WHERE id=?", (quantity, product_id))
    cur.execute(
        """
        INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes)
        VALUES (?,?,?,?,?,?,?)
        """,
        (date_value, product_id, "out", -quantity, "sale", invoice_id, "ط·آ·ط¹آ¾ط·آ·ط¢آ±ط·آ·ط¢آ­ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹"),
    )
    cur.execute(
        """
        UPDATE sales_invoices
        SET status='posted', journal_id=?, tax_journal_id=?, withholding_journal_id=?, cogs_journal_id=?
        WHERE id=?
        """,
        (journal_id, tax_journal_id, withholding_journal_id, cogs_journal_id, invoice_id),
    )


def unpost_sales_invoice(cur, invoice_id):
    cur.execute(
        """
        SELECT product_id,quantity,journal_id,tax_journal_id,withholding_journal_id,cogs_journal_id,status
        FROM sales_invoices
        WHERE id=?
        """,
        (invoice_id,),
    )
    row = cur.fetchone()
    if not row or row[6] != "posted":
        return
    product_id, quantity, journal_id, tax_journal_id, withholding_journal_id, cogs_journal_id, _ = row
    cur.execute("UPDATE products SET stock_quantity=stock_quantity+? WHERE id=?", (quantity, product_id))
    cur.execute("DELETE FROM inventory_movements WHERE reference_type='sale' AND reference_id=?", (invoice_id,))
    delete_journal_rows(cur, journal_id, tax_journal_id, withholding_journal_id, cogs_journal_id)
    cur.execute(
        """
        UPDATE sales_invoices
        SET status='draft', journal_id=NULL, tax_journal_id=NULL, withholding_journal_id=NULL, cogs_journal_id=NULL
        WHERE id=?
        """,
        (invoice_id,),
    )


def post_purchase_invoice(cur, invoice_id):
    cur.execute(
        """
        SELECT date,product_id,quantity,unit_price,total,tax_amount,withholding_amount,payment_type,status
        FROM purchase_invoices
        WHERE id=?
        """,
        (invoice_id,),
    )
    row = cur.fetchone()
    if not row or row[8] != "draft":
        return
    date_value, product_id, quantity, unit_price, total, tax_amount, withholding_amount, payment_type, _ = row
    cur.execute("SELECT name FROM products WHERE id=?", (product_id,))
    product = cur.fetchone()
    if not product:
        raise ValueError(f"ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آµط·آ¸أ¢â‚¬آ ط·آ¸ط¸آ¾ ط·آ·ط·â€؛ط·آ¸ط¸آ¹ط·آ·ط¢آ± ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ¬ط·آ¸ط«â€ ط·آ·ط¢آ¯ ط·آ¸ط¸آ¾ط·آ¸ط¸آ¹ ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ¯ #{invoice_id}.")
    credit_code = "2100" if payment_type == "credit" else "1100"
    journal_id = create_auto_journal(cur, date_value, f"ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ´ط·آ·ط¢آ±ط·آ·ط¢آ§ط·آ·ط·إ’ - {product[0]}", "1400", credit_code, total)
    tax_journal_id = create_auto_journal(cur, date_value, f"ط·آ·ط¢آ¶ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ¨ط·آ·ط¢آ© ط·آ¸أ¢â‚¬ع‘ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ© ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ¶ط·آ·ط¢آ§ط·آ¸ط¸آ¾ط·آ·ط¢آ© ط·آ·ط¢آ¹ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ° ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ´ط·آ·ط¢آ±ط·آ·ط¢آ§ط·آ·ط·إ’ - {product[0]}", "1500", credit_code, tax_amount) if tax_amount > 0 else None
    withholding_debit = "2100" if payment_type == "credit" else "1100"
    withholding_journal_id = create_auto_journal(cur, date_value, f"ضريبة خصم وإضافة مورد على فاتورة مورد - {product[0]}", withholding_debit, "2230", withholding_amount) if withholding_amount > 0 else None
    mark_journal_source(cur, "purchases", invoice_id, journal_id, tax_journal_id, withholding_journal_id)
    cur.execute("UPDATE products SET stock_quantity=stock_quantity+?, purchase_price=? WHERE id=?", (quantity, unit_price, product_id))
    cur.execute(
        """
        INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes)
        VALUES (?,?,?,?,?,?,?)
        """,
        (date_value, product_id, "in", quantity, "purchase", invoice_id, "ط·آ·ط¹آ¾ط·آ·ط¢آ±ط·آ·ط¢آ­ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ¯"),
    )
    cur.execute(
        "UPDATE purchase_invoices SET status='posted', journal_id=?, tax_journal_id=?, withholding_journal_id=? WHERE id=?",
        (journal_id, tax_journal_id, withholding_journal_id, invoice_id),
    )


def unpost_purchase_invoice(cur, invoice_id):
    cur.execute(
        """
        SELECT product_id,quantity,journal_id,tax_journal_id,withholding_journal_id,status
        FROM purchase_invoices
        WHERE id=?
        """,
        (invoice_id,),
    )
    row = cur.fetchone()
    if not row or row[5] != "posted":
        return
    product_id, quantity, journal_id, tax_journal_id, withholding_journal_id, _ = row
    cur.execute("SELECT stock_quantity FROM products WHERE id=?", (product_id,))
    stock = cur.fetchone()
    if not stock or stock[0] < quantity:
        raise ValueError(f"ط·آ·ط¢آ±ط·آ·ط¢آµط·آ¸ط¸آ¹ط·آ·ط¢آ¯ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آµط·آ¸أ¢â‚¬آ ط·آ¸ط¸آ¾ ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ ط·آ¸ط¸آ¹ط·آ¸ط¦â€™ط·آ¸ط¸آ¾ط·آ¸ط¸آ¹ ط·آ¸أ¢â‚¬â€چط·آ¸ط¸آ¾ط·آ¸ط¦â€™ ط·آ·ط¹آ¾ط·آ·ط¢آ±ط·آ·ط¢آ­ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ¯ #{invoice_id}.")
    cur.execute("UPDATE products SET stock_quantity=stock_quantity-? WHERE id=?", (quantity, product_id))
    cur.execute("DELETE FROM inventory_movements WHERE reference_type='purchase' AND reference_id=?", (invoice_id,))
    delete_journal_rows(cur, journal_id, tax_journal_id, withholding_journal_id)
    cur.execute("UPDATE purchase_invoices SET status='draft', journal_id=NULL, tax_journal_id=NULL, withholding_journal_id=NULL WHERE id=?", (invoice_id,))


def post_voucher(cur, table, source_type, voucher_id):
    party_table = "customers" if source_type == "receipts" else "suppliers"
    party_id_col = "customer_id" if source_type == "receipts" else "supplier_id"
    debit_code, credit_code = ("1100", "1300") if source_type == "receipts" else ("2100", "1100")
    label = "ط·آ·ط¢آ³ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¨ط·آ·ط¢آ¶ ط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬آ " if source_type == "receipts" else "ط·آ·ط¢آ³ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯ ط·آ·ط¢آµط·آ·ط¢آ±ط·آ¸ط¸آ¾ ط·آ·ط¢آ¥ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ°"
    cur.execute(
        f"SELECT date,{party_id_col},amount,status FROM {table} WHERE id=?",
        (voucher_id,),
    )
    row = cur.fetchone()
    if not row or row[3] != "draft":
        return
    date_value, party_id, amount, _ = row
    cur.execute(f"SELECT name FROM {party_table} WHERE id=?", (party_id,))
    party = cur.fetchone()
    if not party:
        raise ValueError(f"ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ·ط·آ·ط¢آ±ط·آ¸ط¸آ¾ ط·آ·ط·â€؛ط·آ¸ط¸آ¹ط·آ·ط¢آ± ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ¬ط·آ¸ط«â€ ط·آ·ط¢آ¯ ط·آ¸ط¸آ¾ط·آ¸ط¸آ¹ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ³ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯ #{voucher_id}.")
    journal_id = create_auto_journal(cur, date_value, f"{label} {party[0]}", debit_code, credit_code, amount)
    mark_journal_source(cur, source_type, voucher_id, journal_id)
    cur.execute(f"UPDATE {table} SET status='posted', journal_id=? WHERE id=?", (journal_id, voucher_id))


def unpost_voucher(cur, table, voucher_id):
    cur.execute(f"SELECT journal_id,status FROM {table} WHERE id=?", (voucher_id,))
    row = cur.fetchone()
    if not row or row[1] != "posted":
        return
    delete_journal_rows(cur, row[0])
    cur.execute(f"UPDATE {table} SET status='draft', journal_id=NULL WHERE id=?", (voucher_id,))


def post_group(cur, group_key):
    if group_key == "manual_journal":
        cur.execute("UPDATE journal SET status='posted' WHERE source_type='manual' AND status='draft'")
    elif group_key == "sales":
        cur.execute("SELECT id FROM sales_invoices WHERE status='draft'")
        for (invoice_id,) in cur.fetchall():
            post_sales_invoice(cur, invoice_id)
    elif group_key == "purchases":
        cur.execute("SELECT id FROM purchase_invoices WHERE status='draft'")
        for (invoice_id,) in cur.fetchall():
            post_purchase_invoice(cur, invoice_id)
    elif group_key == "receipts":
        cur.execute("SELECT id FROM receipt_vouchers WHERE status='draft'")
        for (voucher_id,) in cur.fetchall():
            post_voucher(cur, "receipt_vouchers", "receipts", voucher_id)
    elif group_key == "payments":
        cur.execute("SELECT id FROM payment_vouchers WHERE status='draft'")
        for (voucher_id,) in cur.fetchall():
            post_voucher(cur, "payment_vouchers", "payments", voucher_id)


def unpost_group(cur, group_key):
    if group_key == "manual_journal":
        cur.execute("UPDATE journal SET status='draft' WHERE source_type='manual' AND status='posted'")
    elif group_key == "sales":
        cur.execute("SELECT id FROM sales_invoices WHERE status='posted'")
        for (invoice_id,) in cur.fetchall():
            unpost_sales_invoice(cur, invoice_id)
    elif group_key == "purchases":
        cur.execute("SELECT id FROM purchase_invoices WHERE status='posted'")
        for (invoice_id,) in cur.fetchall():
            unpost_purchase_invoice(cur, invoice_id)
    elif group_key == "receipts":
        cur.execute("SELECT id FROM receipt_vouchers WHERE status='posted'")
        for (voucher_id,) in cur.fetchall():
            unpost_voucher(cur, "receipt_vouchers", voucher_id)
    elif group_key == "payments":
        cur.execute("SELECT id FROM payment_vouchers WHERE status='posted'")
        for (voucher_id,) in cur.fetchall():
            unpost_voucher(cur, "payment_vouchers", voucher_id)


def reverse_journal(cur, journal_id, date, reason):
    if not journal_id:
        return None

    cur.execute(
        """
        SELECT debit_account_id, credit_account_id, amount, description
        FROM journal
        WHERE id=?
        """,
        (journal_id,),
    )
    row = cur.fetchone()
    if not row:
        return None

    debit_id, credit_id, amount, description = row
    cur.execute(
        """
        INSERT INTO journal(date,description,debit_account_id,credit_account_id,amount,status,source_type)
        VALUES (?,?,?,?,?,'posted','auto')
        """,
        (date, f"ط·آ¸أ¢â‚¬ع‘ط·آ¸ط¸آ¹ط·آ·ط¢آ¯ ط·آ·ط¢آ¹ط·آ¸ط¦â€™ط·آ·ط¢آ³ط·آ¸ط¸آ¹ - {description} - {reason}", credit_id, debit_id, amount),
    )
    return cur.lastrowid


def parse_positive_amount(value):
    try:
        return float(value or 0)
    except ValueError:
        return 0


def _arabic_under_100(number):
    ones = ["", "واحد", "اثنان", "ثلاثة", "أربعة", "خمسة", "ستة", "سبعة", "ثمانية", "تسعة"]
    tens_words = ["", "عشرة", "عشرون", "ثلاثون", "أربعون", "خمسون", "ستون", "سبعون", "ثمانون", "تسعون"]
    teens = {
        11: "أحد عشر",
        12: "اثنا عشر",
        13: "ثلاثة عشر",
        14: "أربعة عشر",
        15: "خمسة عشر",
        16: "ستة عشر",
        17: "سبعة عشر",
        18: "ثمانية عشر",
        19: "تسعة عشر",
    }
    if number < 10:
        return ones[number]
    if number == 10:
        return "عشرة"
    if 11 <= number <= 19:
        return teens[number]
    unit = number % 10
    ten = number // 10
    return f"{ones[unit]} و{tens_words[ten]}" if unit else tens_words[ten]


def _arabic_under_1000(number):
    hundreds_words = ["", "مائة", "مائتان", "ثلاثمائة", "أربعمائة", "خمسمائة", "ستمائة", "سبعمائة", "ثمانمائة", "تسعمائة"]
    hundreds = number // 100
    remainder = number % 100
    parts = []
    if hundreds:
        parts.append(hundreds_words[hundreds])
    if remainder:
        parts.append(_arabic_under_100(remainder))
    return " و".join(part for part in parts if part)


def amount_to_words(amount):
    amount = round(parse_positive_amount(amount), 2)
    pounds = int(amount)
    piasters = int(round((amount - pounds) * 100))
    if pounds == 0:
        pound_words = "صفر"
    else:
        parts = []
        millions = pounds // 1000000
        thousands = (pounds % 1000000) // 1000
        remainder = pounds % 1000
        if millions:
            if millions == 1:
                parts.append("مليون")
            elif millions == 2:
                parts.append("مليونان")
            else:
                parts.append(f"{_arabic_under_1000(millions)} مليون")
        if thousands:
            if thousands == 1:
                parts.append("ألف")
            elif thousands == 2:
                parts.append("ألفان")
            elif 3 <= thousands <= 10:
                parts.append(f"{_arabic_under_1000(thousands)} آلاف")
            else:
                parts.append(f"{_arabic_under_1000(thousands)} ألف")
        if remainder:
            parts.append(_arabic_under_1000(remainder))
        pound_words = " و".join(part for part in parts if part)
    result = f"فقط {pound_words} جنيها"
    if piasters:
        result += f" و{_arabic_under_1000(piasters)} قرشا"
    return result


def parse_iso_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def ensure_open_period(cur, date_value):
    if not date_value:
        return
    cur.execute(
        """
        SELECT name
        FROM fiscal_periods
        WHERE status='closed' AND ? BETWEEN start_date AND end_date
        LIMIT 1
        """,
        (date_value,),
    )
    row = cur.fetchone()
    if row:
        raise ValueError(f"الفترة المالية {row[0]} مغلقة. افتح الفترة من شاشة الفترات المالية قبل التسجيل أو التعديل داخلها.")


def aging_bucket(due_date, today):
    parsed_due_date = parse_iso_date(due_date) or today
    days_late = (today - parsed_due_date).days
    if days_late <= 0:
        return 0
    if days_late <= 30:
        return 1
    if days_late <= 60:
        return 2
    if days_late <= 90:
        return 3
    return 4


def build_aging_rows(invoice_rows, settlement_rows):
    today = date.today()
    settlements_by_party = {}
    for party_id, amount in settlement_rows:
        settlements_by_party[party_id] = settlements_by_party.get(party_id, 0) + (amount or 0)

    grouped = {}
    for party_id, party_name, invoice_date, due_date, amount in invoice_rows:
        grouped.setdefault(party_id, {"name": party_name, "invoices": []})
        grouped[party_id]["invoices"].append(
            {
                "invoice_date": invoice_date,
                "due_date": due_date or invoice_date,
                "amount": amount or 0,
            }
        )

    rows = []
    for party_id, data in grouped.items():
        remaining_settlement = settlements_by_party.get(party_id, 0)
        buckets = [0, 0, 0, 0, 0]
        invoices = sorted(data["invoices"], key=lambda item: (item["due_date"] or "", item["invoice_date"] or ""))
        for invoice in invoices:
            outstanding = invoice["amount"]
            if remaining_settlement > 0:
                applied = min(outstanding, remaining_settlement)
                outstanding -= applied
                remaining_settlement -= applied
            if outstanding > 0:
                buckets[aging_bucket(invoice["due_date"], today)] += outstanding

        total = sum(buckets)
        if total > 0:
            rows.append((party_id, data["name"], *buckets, total))

    rows.sort(key=lambda row: row[-1], reverse=True)
    totals = [sum(row[index] for row in rows) for index in range(2, 8)]
    return rows, totals


def json_dump(value):
    if value in (None, ""):
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def row_snapshot(cur, table_name, entity_id):
    cur.execute(f"SELECT * FROM {table_name} WHERE id=?", (entity_id,))
    row = cur.fetchone()
    if not row:
        return None
    columns = [description[0] for description in cur.description]
    return dict(zip(columns, row))


def log_action(cur, action, entity_type, entity_id=None, details="", old_values=None, new_values=None):
    cur.execute(
        """
        INSERT INTO audit_log(username,action,entity_type,entity_id,details,old_values,new_values,ip_address,user_agent)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            session.get("username", ""),
            action,
            entity_type,
            entity_id,
            details,
            json_dump(old_values),
            json_dump(new_values),
            request.headers.get("X-Forwarded-For", request.remote_addr or ""),
            (request.headers.get("User-Agent") or "")[:250],
        ),
    )


def party_page(table_name, template_title, success_message):
    conn = db()
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        tax_registration_number = request.form.get("tax_registration_number", "").strip()
        tax_card_number = request.form.get("tax_card_number", "").strip()
        commercial_register = request.form.get("commercial_register", "").strip()
        contact_person = request.form.get("contact_person", "").strip()
        email = request.form.get("email", "").strip()

        if not name:
            flash("ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ط·آ·ط¢آ³ط·آ¸أ¢â‚¬آ¦ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ·ط·آ¸أ¢â‚¬â€چط·آ¸ط«â€ ط·آ·ط¢آ¨.", "danger")
        else:
            cur.execute(
                f"""
                INSERT INTO {table_name}(
                    name,phone,address,tax_registration_number,tax_card_number,
                    commercial_register,contact_person,email
                )
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    name,
                    phone,
                    address,
                    tax_registration_number,
                    tax_card_number,
                    commercial_register,
                    contact_person,
                    email,
                ),
            )
            party_id = cur.lastrowid
            log_action(cur, "create", table_name[:-1], party_id, name)
            conn.commit()
            conn.close()
            flash(success_message, "success")
            return redirect(url_for(table_name))

    cur.execute(
        f"""
        SELECT id,name,phone,address,tax_registration_number,tax_card_number,commercial_register,contact_person,email
        FROM {table_name}
        ORDER BY id DESC
        """
    )
    rows = cur.fetchall()
    conn.close()

    return render_template(
        "parties.html",
        title=template_title,
        rows=rows,
        endpoint=table_name,
    )


@app.route("/customers", methods=["GET", "POST"])
@login_required
@permission_required("customers")
def customers():
    return party_page("customers", "ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¹ط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ط·آ·ط·إ’", "ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬آ¦ ط·آ·ط¢آ¥ط·آ·ط¢آ¶ط·آ·ط¢آ§ط·آ¸ط¸آ¾ط·آ·ط¢آ© ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¹ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ ط·آ·ط¢آ¨ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¬ط·آ·ط¢آ§ط·آ·ط¢آ­.")


@app.route("/customers/<int:id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("customers", write_always=True)
def edit_customer(id):
    return build_party_edit_view(MODULE_DEPS)("customers", "العميل", id)


@app.route("/customers/<int:id>/delete", methods=["POST"])
@login_required
@permission_required("customers", write_always=True)
def delete_customer(id):
    return build_party_delete_view(MODULE_DEPS)("customers", "العميل", id)


@app.route("/suppliers", methods=["GET", "POST"])
@login_required
@permission_required("suppliers")
def suppliers():
    return party_page("suppliers", "ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ¸أ¢â‚¬آ ", "ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬آ¦ ط·آ·ط¢آ¥ط·آ·ط¢آ¶ط·آ·ط¢آ§ط·آ¸ط¸آ¾ط·آ·ط¢آ© ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ¯ ط·آ·ط¢آ¨ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¬ط·آ·ط¢آ§ط·آ·ط¢آ­.")


@app.route("/suppliers/<int:id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("suppliers", write_always=True)
def edit_supplier(id):
    return build_party_edit_view(MODULE_DEPS)("suppliers", "المورد", id)


@app.route("/suppliers/<int:id>/delete", methods=["POST"])
@login_required
@permission_required("suppliers", write_always=True)
def delete_supplier(id):
    return build_party_delete_view(MODULE_DEPS)("suppliers", "المورد", id)


@app.route("/products", methods=["GET", "POST"])
@login_required
@permission_required("inventory")
def products():
    return build_products_view(MODULE_DEPS)()


@app.route("/products/<int:id>/barcode")
@login_required
@permission_required("inventory")
def product_barcode(id):
    return build_product_barcode_view(MODULE_DEPS)(id)
@app.route("/sales", methods=["GET", "POST"])
@login_required
@permission_required("sales")
def sales():
    return build_sales_view(MODULE_DEPS)()
@app.route("/sales-orders", methods=["GET", "POST"])
@login_required
@permission_required("sales")
def sales_orders():
    return build_sales_orders_view(MODULE_DEPS)()
@app.route("/sales-deliveries", methods=["GET", "POST"])
@login_required
@permission_required("sales")
def sales_deliveries():
    return build_sales_deliveries_view(MODULE_DEPS)()
@app.route("/sales/from-delivery", methods=["GET", "POST"])
@login_required
@permission_required("sales")
def sales_invoice_from_delivery():
    return build_sales_invoice_from_delivery_view(MODULE_DEPS)()
@app.route("/sales/financial", methods=["GET", "POST"])
@login_required
@permission_required("sales")
def financial_sales():
    return build_financial_sales_view(MODULE_DEPS)()
@app.route("/purchases", methods=["GET", "POST"])
@login_required
@permission_required("purchases")
def purchases():
    return build_purchases_view(MODULE_DEPS)()
@app.route("/purchase-orders", methods=["GET", "POST"])
@login_required
@permission_required("purchases")
def purchase_orders():
    return build_purchase_orders_view(MODULE_DEPS)()
@app.route("/purchase-receipts", methods=["GET", "POST"])
@login_required
@permission_required("purchases")
def purchase_receipts():
    return build_purchase_receipts_view(MODULE_DEPS)()
@app.route("/purchases/from-receipt", methods=["GET", "POST"])
@login_required
@permission_required("purchases")
def purchase_invoice_from_receipt():
    return build_purchase_invoice_from_receipt_view(MODULE_DEPS)()
@app.route("/inventory")
@login_required
@permission_required("inventory")
def inventory():
    return build_inventory_view(MODULE_DEPS)()
@app.route("/sales/<int:id>/cancel", methods=["POST"])
@login_required
@permission_required("sales", write_always=True)
def cancel_sale(id):
    return build_cancel_sale_view(MODULE_DEPS)(id)
@app.route("/sales/<int:id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("sales", write_always=True)
def edit_sale_invoice(id):
    return build_edit_sale_invoice_view(MODULE_DEPS)(id)
@app.route("/purchases/<int:id>/cancel", methods=["POST"])
@login_required
@permission_required("purchases", write_always=True)
def cancel_purchase(id):
    return build_cancel_purchase_view(MODULE_DEPS)(id)
@app.route("/purchases/<int:id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("purchases", write_always=True)
def edit_purchase_invoice(id):
    return build_edit_purchase_invoice_view(MODULE_DEPS)(id)
@app.route("/receipts", methods=["GET", "POST"])
@login_required
@permission_required("receipts")
def receipts():
    return build_receipts_view(MODULE_DEPS)()
@app.route("/payments", methods=["GET", "POST"])
@login_required
@permission_required("payments")
def payments():
    return build_payments_view(MODULE_DEPS)()
@app.route("/receipts/<int:id>/cancel", methods=["POST"])
@login_required
@permission_required("receipts", write_always=True)
def cancel_receipt(id):
    return build_cancel_receipt_view(MODULE_DEPS)(id)
@app.route("/receipts/<int:id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("receipts", write_always=True)
def edit_receipt(id):
    return build_edit_receipt_view(MODULE_DEPS)(id)
@app.route("/payments/<int:id>/cancel", methods=["POST"])
@login_required
@permission_required("payments", write_always=True)
def cancel_payment(id):
    return build_cancel_payment_view(MODULE_DEPS)(id)
@app.route("/payments/<int:id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("payments", write_always=True)
def edit_payment(id):
    return build_edit_payment_view(MODULE_DEPS)(id)
@app.route("/employees", methods=["GET", "POST"])
@login_required
@permission_required("hr")
def employees():
    return build_employees_view(MODULE_DEPS)()
@app.route("/employees/<int:id>/toggle", methods=["POST"])
@login_required
@permission_required("hr", write_always=True)
def toggle_employee(id):
    return build_toggle_employee_view(MODULE_DEPS)(id)
@app.route("/payroll", methods=["GET", "POST"])
@login_required
@permission_required("hr")
def payroll():
    return build_payroll_view(MODULE_DEPS)()
@app.route("/payroll/<int:id>")
@login_required
@permission_required("hr")
def payroll_details(id):
    return build_payroll_details_view(MODULE_DEPS)(id)
@app.route("/cost-centers", methods=["GET", "POST"])
@login_required
@permission_required("accounting")
def cost_centers():
    conn = db()
    cur = conn.cursor()
    if request.method == "POST":
        code = request.form.get("code", "").strip() or None
        name = request.form.get("name", "").strip()
        center_type = request.form.get("center_type", "").strip()
        notes = request.form.get("notes", "").strip()
        if not name:
            flash("ط·آ·ط¢آ§ط·آ·ط¢آ³ط·آ¸أ¢â‚¬آ¦ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ¸ط¦â€™ط·آ·ط¢آ² ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¹آ¾ط·آ¸ط¦â€™ط·آ¸أ¢â‚¬â€چط·آ¸ط¸آ¾ط·آ·ط¢آ© ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ·ط·آ¸أ¢â‚¬â€چط·آ¸ط«â€ ط·آ·ط¢آ¨.", "danger")
        else:
            try:
                cur.execute(
                    "INSERT INTO cost_centers(code,name,center_type,notes) VALUES (?,?,?,?)",
                    (code, name, center_type, notes),
                )
                center_id = cur.lastrowid
                log_action(cur, "create", "cost_center", center_id, name)
                conn.commit()
                flash("ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬آ¦ ط·آ·ط¢آ¥ط·آ·ط¢آ¶ط·آ·ط¢آ§ط·آ¸ط¸آ¾ط·آ·ط¢آ© ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ¸ط¦â€™ط·آ·ط¢آ² ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¹آ¾ط·آ¸ط¦â€™ط·آ¸أ¢â‚¬â€چط·آ¸ط¸آ¾ط·آ·ط¢آ©.", "success")
                return redirect(url_for("cost_centers"))
            except sqlite3.IntegrityError:
                flash("ط·آ¸ط¦â€™ط·آ¸ط«â€ ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ¸ط¦â€™ط·آ·ط¢آ² ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¹آ¾ط·آ¸ط¦â€™ط·آ¸أ¢â‚¬â€چط·آ¸ط¸آ¾ط·آ·ط¢آ© ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ³ط·آ·ط¹آ¾ط·آ·ط¢آ®ط·آ·ط¢آ¯ط·آ¸أ¢â‚¬آ¦ ط·آ·ط¢آ¨ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸ط¸آ¾ط·آ·ط¢آ¹ط·آ¸أ¢â‚¬â€چ.", "danger")
    cur.execute("SELECT id,code,name,center_type,status,notes FROM cost_centers ORDER BY code,name")
    rows = cur.fetchall()
    conn.close()
    return render_template("cost_centers.html", rows=rows)


@app.route("/document-sequences", methods=["GET", "POST"])
@login_required
@admin_required
def document_sequences():
    conn = db()
    cur = conn.cursor()
    if request.method == "POST":
        doc_type = request.form.get("doc_type", "").strip()
        prefix = request.form.get("prefix", "").strip()
        next_number = int(parse_positive_amount(request.form.get("next_number")) or 1)
        if not doc_type or not prefix or next_number <= 0:
            flash("ط·آ·ط¢آ±ط·آ·ط¢آ§ط·آ·ط¢آ¬ط·آ·ط¢آ¹ ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ§ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ§ط·آ·ط¹آ¾ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ³ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ³ط·آ¸أ¢â‚¬â€چ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ³ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯.", "danger")
        else:
            cur.execute(
                """
                INSERT INTO document_sequences(doc_type,prefix,next_number)
                VALUES (?,?,?)
                ON CONFLICT(doc_type) DO UPDATE SET prefix=excluded.prefix,next_number=excluded.next_number
                """,
                (doc_type, prefix, next_number),
            )
            log_action(cur, "update", "document_sequence", None, doc_type)
            conn.commit()
            flash("ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬آ¦ ط·آ·ط¢آ­ط·آ¸ط¸آ¾ط·آ·ط¢آ¸ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ³ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ³ط·آ¸أ¢â‚¬â€چ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ³ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯.", "success")
            return redirect(url_for("document_sequences"))
    cur.execute("SELECT doc_type,prefix,next_number FROM document_sequences ORDER BY doc_type")
    rows = cur.fetchall()
    conn.close()
    return render_template("document_sequences.html", rows=rows)


@app.route("/sales/multi", methods=["GET", "POST"])
@login_required
@permission_required("sales")
def sales_multi():
    conn = db()
    cur = conn.cursor()
    if request.method == "POST":
        date_value = request.form.get("date", "").strip()
        due_date = request.form.get("due_date", "").strip()
        customer_id = request.form.get("customer_id") or None
        payment_type = request.form.get("payment_type", "cash")
        tax_rate = parse_positive_amount(request.form.get("tax_rate", DEFAULT_TAX_RATE))
        lines = get_form_lines(cur)
        if not date_value or not lines:
            flash("ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¹آ¾ط·آ·ط¢آ§ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ® ط·آ¸ط«â€ ط·آ·ط¢آ¨ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯ ط·آ¸ط«â€ ط·آ·ط¢آ§ط·آ·ط¢آ­ط·آ·ط¢آ¯ ط·آ·ط¢آ¹ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ° ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ£ط·آ¸أ¢â‚¬ع‘ط·آ¸أ¢â‚¬â€چ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ·ط·آ¸أ¢â‚¬â€چط·آ¸ط«â€ ط·آ·ط¢آ¨ط·آ·ط¢آ§ط·آ¸أ¢â‚¬آ .", "danger")
        elif payment_type == "credit" and not customer_id:
            flash("ط·آ·ط¢آ§ط·آ·ط¢آ®ط·آ·ط¹آ¾ط·آ·ط¢آ± ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¹ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ ط·آ·ط¢آ¹ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¢ط·آ·ط¢آ¬ط·آ¸أ¢â‚¬â€چ.", "danger")
        elif any(line["stock_quantity"] < line["quantity"] for line in lines):
            flash("ط·آ·ط¢آ±ط·آ·ط¢آµط·آ¸ط¸آ¹ط·آ·ط¢آ¯ ط·آ·ط¢آ£ط·آ·ط¢آ­ط·آ·ط¢آ¯ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ£ط·آ·ط¢آµط·آ¸أ¢â‚¬آ ط·آ·ط¢آ§ط·آ¸ط¸آ¾ ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ ط·آ¸ط¸آ¹ط·آ¸ط¦â€™ط·آ¸ط¸آ¾ط·آ¸ط¸آ¹.", "danger")
        else:
            try:
                ensure_open_period(cur, date_value)
            except ValueError as exc:
                flash(str(exc), "danger")
                conn.close()
                return redirect(url_for("sales_multi"))
            total = sum(line["total"] for line in lines)
            cost_total = sum(line["cost_total"] for line in lines)
            tax_amount = total * tax_rate / 100
            grand_total = total + tax_amount
            first_line = lines[0]
            doc_no = next_document_number(cur, "sales")
            debit_code = "1300" if payment_type == "credit" else "1100"
            journal_id = create_auto_journal(cur, date_value, f"ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¹آ¾ط·آ·ط¢آ¹ط·آ·ط¢آ¯ط·آ·ط¢آ¯ط·آ·ط¢آ© ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¨ط·آ¸أ¢â‚¬آ ط·آ¸ط«â€ ط·آ·ط¢آ¯ {doc_no}", debit_code, "4100", total)
            tax_journal_id = create_auto_journal(cur, date_value, f"ط·آ·ط¢آ¶ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ¨ط·آ·ط¢آ© ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ {doc_no}", debit_code, "2200", tax_amount) if tax_amount > 0 else None
            cogs_journal_id = create_auto_journal(cur, date_value, f"ط·آ·ط¹آ¾ط·آ¸ط¦â€™ط·آ¸أ¢â‚¬â€چط·آ¸ط¸آ¾ط·آ·ط¢آ© ط·آ·ط¢آ¨ط·آ·ط¢آ¶ط·آ·ط¢آ§ط·آ·ط¢آ¹ط·آ·ط¢آ© ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ¨ط·آ·ط¢آ§ط·آ·ط¢آ¹ط·آ·ط¢آ© {doc_no}", "6100", "1400", cost_total) if cost_total > 0 else None
            cur.execute(
                """
                INSERT INTO sales_invoices(
                    date,due_date,doc_no,customer_id,product_id,quantity,unit_price,total,cost_total,
                    tax_rate,tax_amount,grand_total,payment_type,journal_id,tax_journal_id,cogs_journal_id,status
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    date_value, due_date, doc_no, customer_id, first_line["product_id"], 1, total, total,
                    cost_total, tax_rate, tax_amount, grand_total, payment_type, journal_id, tax_journal_id,
                    cogs_journal_id, "posted",
                ),
            )
            invoice_id = cur.lastrowid
            mark_journal_source(cur, "sales", invoice_id, journal_id, tax_journal_id, cogs_journal_id)
            for line in lines:
                cur.execute(
                    """
                    INSERT INTO sales_invoice_lines(invoice_id,product_id,quantity,unit_price,total,cost_total)
                    VALUES (?,?,?,?,?,?)
                    """,
                    (invoice_id, line["product_id"], line["quantity"], line["unit_price"], line["total"], line["cost_total"]),
                )
                cur.execute("UPDATE products SET stock_quantity=stock_quantity-? WHERE id=?", (line["quantity"], line["product_id"]))
                cur.execute(
                    """
                    INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (date_value, line["product_id"], "out", -line["quantity"], "sale", invoice_id, f"ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ {doc_no}"),
                )
            log_action(cur, "create", "sales_invoice", invoice_id, doc_no)
            conn.commit()
            conn.close()
            rebuild_ledger()
            flash(f"ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬آ¦ ط·آ·ط¢آ­ط·آ¸ط¸آ¾ط·آ·ط¢آ¸ ط·آ¸ط«â€ ط·آ·ط¹آ¾ط·آ·ط¢آ±ط·آ·ط¢آ­ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ {doc_no}.", "success")
            return redirect(url_for("sales"))
    cur.execute("SELECT id,name FROM customers ORDER BY name")
    customers_rows = cur.fetchall()
    cur.execute("SELECT id,name,sale_price,stock_quantity FROM products ORDER BY name")
    product_rows = cur.fetchall()
    conn.close()
    return render_template("multi_invoice.html", title="ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¹آ¾ط·آ·ط¢آ¹ط·آ·ط¢آ¯ط·آ·ط¢آ¯ط·آ·ط¢آ© ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¨ط·آ¸أ¢â‚¬آ ط·آ¸ط«â€ ط·آ·ط¢آ¯", customers=customers_rows, suppliers=[], products=product_rows, action_url=url_for("sales_multi"), party="customer")


@app.route("/purchases/multi", methods=["GET", "POST"])
@login_required
@permission_required("purchases")
def purchases_multi():
    conn = db()
    cur = conn.cursor()
    if request.method == "POST":
        date_value = request.form.get("date", "").strip()
        supplier_id = request.form.get("supplier_id") or None
        payment_type = request.form.get("payment_type", "cash")
        tax_rate = parse_positive_amount(request.form.get("tax_rate", DEFAULT_TAX_RATE))
        supplier_invoice_no = request.form.get("supplier_invoice_no", "").strip()
        supplier_invoice_date = request.form.get("supplier_invoice_date", "").strip()
        due_date = request.form.get("due_date", "").strip()
        lines = get_form_lines(cur)
        if not date_value or not supplier_invoice_no or not supplier_invoice_date or not lines:
            flash("ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ§ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ§ط·آ·ط¹آ¾ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ¸ط«â€ ط·آ·ط¢آ¨ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯ ط·آ¸ط«â€ ط·آ·ط¢آ§ط·آ·ط¢آ­ط·آ·ط¢آ¯ ط·آ·ط¢آ¹ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ° ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ£ط·آ¸أ¢â‚¬ع‘ط·آ¸أ¢â‚¬â€چ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ·ط·آ¸أ¢â‚¬â€چط·آ¸ط«â€ ط·آ·ط¢آ¨ط·آ·ط¢آ©.", "danger")
        elif payment_type == "credit" and not supplier_id:
            flash("ط·آ·ط¢آ§ط·آ·ط¢آ®ط·آ·ط¹آ¾ط·آ·ط¢آ± ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ¯ ط·آ·ط¢آ¹ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ´ط·آ·ط¢آ±ط·آ·ط¢آ§ط·آ·ط·إ’ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¢ط·آ·ط¢آ¬ط·آ¸أ¢â‚¬â€چ.", "danger")
        else:
            try:
                ensure_open_period(cur, date_value)
            except ValueError as exc:
                flash(str(exc), "danger")
                conn.close()
                return redirect(url_for("purchases_multi"))
            total = sum(line["total"] for line in lines)
            tax_amount = total * tax_rate / 100
            grand_total = total + tax_amount
            first_line = lines[0]
            doc_no = next_document_number(cur, "purchases")
            credit_code = "2100" if payment_type == "credit" else "1100"
            journal_id = create_auto_journal(cur, date_value, f"ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¹آ¾ط·آ·ط¢آ¹ط·آ·ط¢آ¯ط·آ·ط¢آ¯ط·آ·ط¢آ© ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¨ط·آ¸أ¢â‚¬آ ط·آ¸ط«â€ ط·آ·ط¢آ¯ {doc_no}", "1400", credit_code, total)
            tax_journal_id = create_auto_journal(cur, date_value, f"ط·آ·ط¢آ¶ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ¨ط·آ·ط¢آ© ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ¯ {doc_no}", "1500", credit_code, tax_amount) if tax_amount > 0 else None
            cur.execute(
                """
                INSERT INTO purchase_invoices(
                    date,doc_no,supplier_invoice_no,supplier_invoice_date,due_date,supplier_id,product_id,
                    quantity,unit_price,total,tax_rate,tax_amount,grand_total,payment_type,journal_id,tax_journal_id,status,notes
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    date_value, doc_no, supplier_invoice_no, supplier_invoice_date, due_date, supplier_id, first_line["product_id"],
                    1, total, total, tax_rate, tax_amount, grand_total, payment_type, journal_id, tax_journal_id, "posted",
                    "ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ¸أ¢â‚¬آ¦ط·آ·ط¹آ¾ط·آ·ط¢آ¹ط·آ·ط¢آ¯ط·آ·ط¢آ¯ط·آ·ط¢آ© ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¨ط·آ¸أ¢â‚¬آ ط·آ¸ط«â€ ط·آ·ط¢آ¯",
                ),
            )
            invoice_id = cur.lastrowid
            mark_journal_source(cur, "purchases", invoice_id, journal_id, tax_journal_id)
            for line in lines:
                cur.execute(
                    """
                    INSERT INTO purchase_invoice_lines(invoice_id,product_id,quantity,unit_price,total)
                    VALUES (?,?,?,?,?)
                    """,
                    (invoice_id, line["product_id"], line["quantity"], line["unit_price"], line["total"]),
                )
                cur.execute(
                    "UPDATE products SET stock_quantity=stock_quantity+?, purchase_price=? WHERE id=?",
                    (line["quantity"], line["unit_price"], line["product_id"]),
                )
                cur.execute(
                    """
                    INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (date_value, line["product_id"], "in", line["quantity"], "purchase", invoice_id, f"ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ¯ {doc_no}"),
                )
            log_action(cur, "create", "purchase_invoice", invoice_id, doc_no)
            conn.commit()
            conn.close()
            rebuild_ledger()
            flash(f"ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬آ¦ ط·آ·ط¢آ­ط·آ¸ط¸آ¾ط·آ·ط¢آ¸ ط·آ¸ط«â€ ط·آ·ط¹آ¾ط·آ·ط¢آ±ط·آ·ط¢آ­ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ¯ {doc_no}.", "success")
            return redirect(url_for("purchases"))
    cur.execute("SELECT id,name FROM suppliers ORDER BY name")
    suppliers_rows = cur.fetchall()
    cur.execute("SELECT id,name,purchase_price,stock_quantity FROM products ORDER BY name")
    product_rows = cur.fetchall()
    conn.close()
    return render_template("multi_invoice.html", title="ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¹آ¾ط·آ·ط¢آ¹ط·آ·ط¢آ¯ط·آ·ط¢آ¯ط·آ·ط¢آ© ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¨ط·آ¸أ¢â‚¬آ ط·آ¸ط«â€ ط·آ·ط¢آ¯", customers=[], suppliers=suppliers_rows, products=product_rows, action_url=url_for("purchases_multi"), party="supplier")


@app.route("/sales/<int:id>/print")
@login_required
@permission_required("sales")
def print_sale(id):
    return build_print_sale_view(MODULE_DEPS)(id)
@app.route("/purchases/<int:id>/print")
@login_required
@permission_required("purchases")
def print_purchase(id):
    return build_print_purchase_view(MODULE_DEPS)(id)
@app.route("/purchase-orders/<int:id>/print")
@login_required
@permission_required("purchases")
def print_purchase_order(id):
    return build_print_purchase_order_view(MODULE_DEPS)(id)
def _order_lines_from_form(cur):
    product_ids = request.form.getlist("product_id[]") or request.form.getlist("product_id")
    quantities = request.form.getlist("quantity[]") or request.form.getlist("quantity")
    unit_prices = request.form.getlist("unit_price[]") or request.form.getlist("unit_price")
    tax_rates = request.form.getlist("tax_rate[]") or request.form.getlist("tax_rate")
    lines = []
    for idx, product_id in enumerate(product_ids):
        product_id = (product_id or "").strip()
        quantity = parse_positive_amount(quantities[idx] if idx < len(quantities) else 0)
        unit_price = parse_positive_amount(unit_prices[idx] if idx < len(unit_prices) else 0)
        tax_rate = parse_positive_amount(tax_rates[idx] if idx < len(tax_rates) else DEFAULT_TAX_RATE)
        if not product_id and quantity == 0 and unit_price == 0:
            continue
        cur.execute("SELECT 1 FROM products WHERE id=?", (product_id,))
        if not cur.fetchone() or quantity <= 0 or unit_price <= 0:
            return []
        total = quantity * unit_price
        tax_amount = total * tax_rate / 100
        lines.append((int(product_id), quantity, unit_price, total, tax_rate, tax_amount, total + tax_amount))
    return lines


def _sales_orders_v2():
    conn = db()
    cur = conn.cursor()
    if request.method == "POST":
        date_value = request.form.get("date", "").strip()
        customer_id = request.form.get("customer_id") or None
        payment_terms = request.form.get("payment_terms", "").strip()
        delivery_date = request.form.get("delivery_date", "").strip()
        notes = request.form.get("notes", "").strip()
        lines = _order_lines_from_form(cur)
        order_date = parse_iso_date(date_value)
        requested_delivery = parse_iso_date(delivery_date)
        if not date_value:
            flash("ط·آ·ط¹آ¾ط·آ·ط¢آ§ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ® ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ± ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ·ط·آ¸أ¢â‚¬â€چط·آ¸ط«â€ ط·آ·ط¢آ¨.", "danger")
        elif not lines:
            flash("ط·آ·ط¢آ£ط·آ·ط¢آ¶ط·آ¸ط¸آ¾ ط·آ·ط¢آµط·آ¸أ¢â‚¬آ ط·آ¸ط¸آ¾ط·آ·ط¢آ§ ط·آ¸ط«â€ ط·آ·ط¢آ§ط·آ·ط¢آ­ط·آ·ط¢آ¯ط·آ·ط¢آ§ ط·آ·ط¢آ¹ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ° ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ£ط·آ¸أ¢â‚¬ع‘ط·آ¸أ¢â‚¬â€چ ط·آ·ط¢آ¨ط·آ¸ط¦â€™ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¸آ¹ط·آ·ط¢آ© ط·آ¸ط«â€ ط·آ·ط¢آ³ط·آ·ط¢آ¹ط·آ·ط¢آ± ط·آ·ط¢آµط·آ·ط¢آ­ط·آ¸ط¸آ¹ط·آ·ط¢آ­ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬آ .", "danger")
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
                (date_value, customer_id, first_line[0], quantity, total / quantity if quantity else first_line[2], total, first_line[4], tax_amount, grand_total, payment_terms, delivery_date, notes, "issued"),
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
            flash("ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬آ¦ ط·آ·ط¢آ­ط·آ¸ط¸آ¾ط·آ·ط¢آ¸ ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ± ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¹آ¾ط·آ·ط¢آ¹ط·آ·ط¢آ¯ط·آ·ط¢آ¯ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ£ط·آ·ط¢آµط·آ¸أ¢â‚¬آ ط·آ·ط¢آ§ط·آ¸ط¸آ¾.", "success")
            return redirect(url_for("sales_orders"))

    cur.execute("SELECT id,name FROM customers ORDER BY name")
    customers_rows = cur.fetchall()
    cur.execute("SELECT id,name,sale_price,stock_quantity FROM products ORDER BY name")
    product_rows = cur.fetchall()
    cur.execute(
        """
        SELECT so.id,so.date,COALESCE(c.name,'ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ ط·آ¸أ¢â‚¬آ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¯ط·آ¸ط¸آ¹'),COUNT(sol.id),so.quantity,so.grand_total,so.delivery_date,so.status
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


def _purchase_orders_v2():
    conn = db()
    cur = conn.cursor()
    if request.method == "POST":
        date_value = request.form.get("date", "").strip()
        supplier_id = request.form.get("supplier_id")
        payment_terms = request.form.get("payment_terms", "").strip()
        delivery_date = request.form.get("delivery_date", "").strip()
        delivery_terms = request.form.get("delivery_terms", "").strip()
        notes = request.form.get("notes", "").strip()
        lines = _order_lines_from_form(cur)
        order_date = parse_iso_date(date_value)
        requested_delivery = parse_iso_date(delivery_date)
        cur.execute("SELECT 1 FROM suppliers WHERE id=?", (supplier_id,))
        supplier = cur.fetchone()
        if not date_value:
            flash("ط·آ·ط¹آ¾ط·آ·ط¢آ§ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ® ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ± ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ´ط·آ·ط¢آ±ط·آ·ط¢آ§ط·آ·ط·إ’ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ·ط·آ¸أ¢â‚¬â€چط·آ¸ط«â€ ط·آ·ط¢آ¨.", "danger")
        elif not supplier:
            flash("ط·آ·ط¢آ§ط·آ·ط¢آ®ط·آ·ط¹آ¾ط·آ·ط¢آ± ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ¯.", "danger")
        elif requested_delivery and order_date and requested_delivery < order_date:
            flash("ط·آ·ط¹آ¾ط·آ·ط¢آ§ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ® ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¦â€™ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ  ط·آ¸ط¸آ¹ط·آ¸ط¦â€™ط·آ¸ط«â€ ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ£ط·آ·ط¢آ³ط·آ·ط¢آ¨ط·آ¸أ¢â‚¬ع‘ ط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬آ  ط·آ·ط¹آ¾ط·آ·ط¢آ§ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ® ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ± ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ´ط·آ·ط¢آ±ط·آ·ط¢آ§ط·آ·ط·إ’.", "danger")
        elif not lines:
            flash("ط·آ·ط¢آ£ط·آ·ط¢آ¶ط·آ¸ط¸آ¾ ط·آ·ط¢آµط·آ¸أ¢â‚¬آ ط·آ¸ط¸آ¾ط·آ·ط¢آ§ ط·آ¸ط«â€ ط·آ·ط¢آ§ط·آ·ط¢آ­ط·آ·ط¢آ¯ط·آ·ط¢آ§ ط·آ·ط¢آ¹ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ° ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ£ط·آ¸أ¢â‚¬ع‘ط·آ¸أ¢â‚¬â€چ ط·آ·ط¢آ¨ط·آ¸ط¦â€™ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¸آ¹ط·آ·ط¢آ© ط·آ¸ط«â€ ط·آ·ط¢آ³ط·آ·ط¢آ¹ط·آ·ط¢آ± ط·آ·ط¢آµط·آ·ط¢آ­ط·آ¸ط¸آ¹ط·آ·ط¢آ­ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬آ .", "danger")
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
                (date_value, supplier_id, first_line[0], quantity, total / quantity if quantity else first_line[2], total, first_line[4], tax_amount, grand_total, payment_terms, delivery_date, delivery_terms, notes, "issued"),
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
            flash("ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬آ¦ ط·آ·ط¢آ­ط·آ¸ط¸آ¾ط·آ·ط¢آ¸ ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ± ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ´ط·آ·ط¢آ±ط·آ·ط¢آ§ط·آ·ط·إ’ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¹آ¾ط·آ·ط¢آ¹ط·آ·ط¢آ¯ط·آ·ط¢آ¯ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ£ط·آ·ط¢آµط·آ¸أ¢â‚¬آ ط·آ·ط¢آ§ط·آ¸ط¸آ¾.", "success")
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


def _sales_deliveries_v2():
    conn = db()
    cur = conn.cursor()
    if request.method == "POST":
        date_value = request.form.get("date", "").strip()
        line_id = int(parse_positive_amount(request.form.get("sales_order_line_id")) or 0)
        delivered_quantity = parse_positive_amount(request.form.get("delivered_quantity"))
        notes = request.form.get("notes", "").strip()
        cur.execute(
            """
            SELECT so.id,sol.id,so.customer_id,sol.product_id,sol.quantity,sol.unit_price,sol.tax_rate,p.name,p.purchase_price,p.stock_quantity
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
        if not date_value:
            flash("ط·آ·ط¹آ¾ط·آ·ط¢آ§ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ® ط·آ·ط¢آ¥ط·آ·ط¢آ°ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آµط·آ·ط¢آ±ط·آ¸ط¸آ¾ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ·ط·آ¸أ¢â‚¬â€چط·آ¸ط«â€ ط·آ·ط¢آ¨.", "danger")
        elif not order:
            flash("ط·آ·ط¢آ¨ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯ ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ± ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ ط·آ·ط·â€؛ط·آ¸ط¸آ¹ط·آ·ط¢آ± ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ¬ط·آ¸ط«â€ ط·آ·ط¢آ¯.", "danger")
        elif delivered_quantity <= 0 or delivered_quantity > remaining:
            flash("ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸ط¦â€™ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¸آ¹ط·آ·ط¢آ© ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬آ ط·آ·ط¢آµط·آ·ط¢آ±ط·آ¸ط¸آ¾ط·آ·ط¢آ© ط·آ¸ط¸آ¹ط·آ·ط¢آ¬ط·آ·ط¢آ¨ ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ  ط·آ·ط¹آ¾ط·آ¸ط¦â€™ط·آ¸ط«â€ ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ£ط·آ¸ط¦â€™ط·آ·ط¢آ¨ط·آ·ط¢آ± ط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آµط·آ¸ط¸آ¾ط·آ·ط¢آ± ط·آ¸ط«â€ ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ ط·آ·ط¹آ¾ط·آ·ط¹آ¾ط·آ·ط¢آ¬ط·آ·ط¢آ§ط·آ¸ط«â€ ط·آ·ط¢آ² ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ·ط¹آ¾ط·آ·ط¢آ¨ط·آ¸أ¢â‚¬ع‘ط·آ¸ط¸آ¹.", "danger")
        elif delivered_quantity > order[9]:
            flash("ط·آ·ط¢آ±ط·آ·ط¢آµط·آ¸ط¸آ¹ط·آ·ط¢آ¯ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ®ط·آ·ط¢آ²ط·آ¸ط«â€ ط·آ¸أ¢â‚¬آ  ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ ط·آ¸ط¸آ¹ط·آ¸ط¦â€™ط·آ¸ط¸آ¾ط·آ¸ط¸آ¹ ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¥ط·آ·ط¢آ°ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آµط·آ·ط¢آ±ط·آ¸ط¸آ¾.", "danger")
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
            cogs_journal_id = create_auto_journal(cur, date_value, f"ط·آ·ط¢آ¥ط·آ·ط¢آ°ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آµط·آ·ط¢آ±ط·آ¸ط¸آ¾ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ط·آ·ط¢آ§ط·آ·ط¹آ¾ {delivery_no} - {order[7]}", "6100", "1400", cost_total) if cost_total > 0 else None
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
                (date_value, order[3], "out", -delivered_quantity, "sales_delivery", delivery_id, f"ط·آ·ط¢آ¥ط·آ·ط¢آ°ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آµط·آ·ط¢آ±ط·آ¸ط¸آ¾ {delivery_no}"),
            )
            log_action(cur, "create", "sales_delivery", delivery_id, f"{delivery_no}; total={grand_total}")
            conn.commit()
            conn.close()
            rebuild_ledger()
            flash(f"ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬آ¦ ط·آ·ط¹آ¾ط·آ·ط¢آ³ط·آ·ط¢آ¬ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ ط·آ·ط¢آ¥ط·آ·ط¢آ°ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آµط·آ·ط¢آ±ط·آ¸ط¸آ¾ {delivery_no}.", "success")
            return redirect(url_for("sales_deliveries"))

    cur.execute(
        """
        SELECT sol.id,so.id,so.date,COALESCE(c.name,'ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ ط·آ¸أ¢â‚¬آ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¯ط·آ¸ط¸آ¹'),p.name,sol.quantity,sol.unit_price,
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
        SELECT sd.id,sd.delivery_no,sd.date,sd.sales_order_id,COALESCE(c.name,'ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ ط·آ¸أ¢â‚¬آ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¯ط·آ¸ط¸آ¹'),p.name,
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


def _purchase_receipts_v2():
    conn = db()
    cur = conn.cursor()
    if request.method == "POST":
        date_value = request.form.get("date", "").strip()
        line_id = int(parse_positive_amount(request.form.get("purchase_order_line_id")) or 0)
        received_quantity = parse_positive_amount(request.form.get("received_quantity"))
        notes = request.form.get("notes", "").strip()
        cur.execute(
            """
            SELECT po.id,pol.id,po.supplier_id,pol.product_id,pol.quantity,pol.unit_price,pol.tax_rate,p.name
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
        if not date_value:
            flash("ط·آ·ط¹آ¾ط·آ·ط¢آ§ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ® ط·آ·ط¢آ¥ط·آ·ط¢آ°ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ط·آ·ط¢آ³ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ط·آ¸أ¢â‚¬آ¦ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ·ط·آ¸أ¢â‚¬â€چط·آ¸ط«â€ ط·آ·ط¢آ¨.", "danger")
        elif not order:
            flash("ط·آ·ط¢آ¨ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯ ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ± ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ´ط·آ·ط¢آ±ط·آ·ط¢آ§ط·آ·ط·إ’ ط·آ·ط·â€؛ط·آ¸ط¸آ¹ط·آ·ط¢آ± ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ¬ط·آ¸ط«â€ ط·آ·ط¢آ¯.", "danger")
        elif received_quantity <= 0 or received_quantity > remaining:
            flash("ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸ط¦â€™ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¸آ¹ط·آ·ط¢آ© ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ³ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ© ط·آ¸ط¸آ¹ط·آ·ط¢آ¬ط·آ·ط¢آ¨ ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ  ط·آ·ط¹آ¾ط·آ¸ط¦â€™ط·آ¸ط«â€ ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ£ط·آ¸ط¦â€™ط·آ·ط¢آ¨ط·آ·ط¢آ± ط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آµط·آ¸ط¸آ¾ط·آ·ط¢آ± ط·آ¸ط«â€ ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ ط·آ·ط¹آ¾ط·آ·ط¹آ¾ط·آ·ط¢آ¬ط·آ·ط¢آ§ط·آ¸ط«â€ ط·آ·ط¢آ² ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ·ط¹آ¾ط·آ·ط¢آ¨ط·آ¸أ¢â‚¬ع‘ط·آ¸ط¸آ¹.", "danger")
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
            journal_id = create_auto_journal(cur, date_value, f"ط·آ·ط¢آ¥ط·آ·ط¢آ°ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ§ط·آ·ط¢آ³ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ط·آ¸أ¢â‚¬آ¦ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ®ط·آ·ط¢آ²ط·آ¸أ¢â‚¬آ ط·آ¸ط¸آ¹ {receipt_no} - {order[7]}", "1400", "2150", total)
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
                (date_value, order[3], "in", received_quantity, "purchase_receipt", receipt_id, f"ط·آ·ط¢آ¥ط·آ·ط¢آ°ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ§ط·آ·ط¢آ³ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ط·آ¸أ¢â‚¬آ¦ {receipt_no}"),
            )
            log_action(cur, "create", "purchase_receipt", receipt_id, f"{receipt_no}; total={grand_total}")
            conn.commit()
            conn.close()
            rebuild_ledger()
            flash(f"ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬آ¦ ط·آ·ط¹آ¾ط·آ·ط¢آ³ط·آ·ط¢آ¬ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ ط·آ·ط¢آ¥ط·آ·ط¢آ°ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ط·آ·ط¢آ³ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ط·آ¸أ¢â‚¬آ¦ {receipt_no}.", "success")
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
               pr.received_quantity,pr.unit_price,pr.grand_total,pr.status,pr.invoice_id
        FROM purchase_receipts pr
        JOIN suppliers s ON s.id=pr.supplier_id
        JOIN products p ON p.id=pr.product_id
        ORDER BY pr.id DESC
        """
    )
    rows = cur.fetchall()
    conn.close()
    return render_template("purchase_receipts.html", open_orders=open_orders, rows=rows)


def _print_purchase_order_v2(id):
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
        flash("ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ± ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ´ط·آ·ط¢آ±ط·آ·ط¢آ§ط·آ·ط·إ’ ط·آ·ط·â€؛ط·آ¸ط¸آ¹ط·آ·ط¢آ± ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ¬ط·آ¸ط«â€ ط·آ·ط¢آ¯.", "danger")
        return redirect(url_for("purchase_orders"))
    return render_template("print_purchase_order.html", company=company, order=order, lines=lines)


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
    return result


def _products_v2():
    conn = db()
    cur = conn.cursor()
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        name = request.form.get("name", "").strip()
        unit = request.form.get("unit", "ط·آ¸ط«â€ ط·آ·ط¢آ­ط·آ·ط¢آ¯ط·آ·ط¢آ©").strip() or "ط·آ¸ط«â€ ط·آ·ط¢آ­ط·آ·ط¢آ¯ط·آ·ط¢آ©"
        supplier_id = request.form.get("default_supplier_id") or None
        try:
            purchase_price = float(request.form.get("purchase_price", 0) or 0)
            sale_price = float(request.form.get("sale_price", 0) or 0)
        except ValueError:
            purchase_price = 0
            sale_price = 0
            flash("ط·آ·ط¢آ£ط·آ·ط¢آ³ط·آ·ط¢آ¹ط·آ·ط¢آ§ط·آ·ط¢آ± ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬آ ط·آ·ط¹آ¾ط·آ·ط¢آ¬ ط·آ¸ط¸آ¹ط·آ·ط¢آ¬ط·آ·ط¢آ¨ ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ  ط·آ·ط¹آ¾ط·آ¸ط¦â€™ط·آ¸ط«â€ ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ£ط·آ·ط¢آ±ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ§ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ§.", "danger")
            supplier_id = None
        if supplier_id:
            cur.execute("SELECT 1 FROM suppliers WHERE id=?", (supplier_id,))
            if not cur.fetchone():
                supplier_id = None
        if not name:
            flash("ط·آ·ط¢آ§ط·آ·ط¢آ³ط·آ¸أ¢â‚¬آ¦ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬آ ط·آ·ط¹آ¾ط·آ·ط¢آ¬ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ·ط·آ¸أ¢â‚¬â€چط·آ¸ط«â€ ط·آ·ط¢آ¨.", "danger")
        elif purchase_price < 0 or sale_price < 0:
            flash("ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ£ط·آ·ط¢آ³ط·آ·ط¢آ¹ط·آ·ط¢آ§ط·آ·ط¢آ± ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¦â€™ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ  ط·آ·ط¹آ¾ط·آ¸ط¦â€™ط·آ¸ط«â€ ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ³ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¨ط·آ·ط¢آ©.", "danger")
        else:
            try:
                cur.execute(
                    "INSERT INTO products(code,name,unit,purchase_price,sale_price,default_supplier_id) VALUES (?,?,?,?,?,?)",
                    (code or None, name, unit, purchase_price, sale_price, supplier_id),
                )
                conn.commit()
                conn.close()
                flash("ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬آ¦ط·آ·ط¹آ¾ ط·آ·ط¢آ¥ط·آ·ط¢آ¶ط·آ·ط¢آ§ط·آ¸ط¸آ¾ط·آ·ط¢آ© ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آµط·آ¸أ¢â‚¬آ ط·آ¸ط¸آ¾.", "success")
                return redirect(url_for("products"))
            except sqlite3.IntegrityError:
                flash("ط·آ¸ط¦â€™ط·آ¸ط«â€ ط·آ·ط¢آ¯ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آµط·آ¸أ¢â‚¬آ ط·آ¸ط¸آ¾ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ³ط·آ·ط¹آ¾ط·آ·ط¢آ®ط·آ·ط¢آ¯ط·آ¸أ¢â‚¬آ¦ ط·آ·ط¢آ¨ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸ط¸آ¾ط·آ·ط¢آ¹ط·آ¸أ¢â‚¬â€چ.", "danger")
    cur.execute("SELECT id,name FROM suppliers ORDER BY name")
    suppliers_rows = cur.fetchall()
    cur.execute(
        """
        SELECT p.id,p.code,p.name,p.unit,p.purchase_price,p.sale_price,p.stock_quantity,COALESCE(s.name,'')
        FROM products p
        LEFT JOIN suppliers s ON s.id=p.default_supplier_id
        ORDER BY p.id DESC
        """
    )
    rows = cur.fetchall()
    conn.close()
    return render_template("products.html", products=rows, suppliers=suppliers_rows)


@app.route("/products/<int:id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("inventory", write_always=True)
def edit_product(id):
    return build_edit_product_view(MODULE_DEPS)(id)
@app.route("/products/<int:id>/delete", methods=["POST"])
@login_required
@permission_required("inventory", write_always=True)
def delete_product(id):
    return build_delete_product_view(MODULE_DEPS)(id)
def _employees_v2():
    conn = db()
    cur = conn.cursor()
    if request.method == "POST":
        code = request.form.get("code", "").strip() or None
        name = request.form.get("name", "").strip()
        department = request.form.get("department", "").strip()
        job_title = request.form.get("job_title", "").strip()
        hire_date = request.form.get("hire_date", "").strip()
        base_salary = parse_positive_amount(request.form.get("base_salary"))
        allowances = parse_positive_amount(request.form.get("allowances"))
        insurance_employee = parse_positive_amount(request.form.get("insurance_employee"))
        insurance_company = parse_positive_amount(request.form.get("insurance_company"))
        tax = parse_positive_amount(request.form.get("tax"))
        notes = request.form.get("notes", "").strip()
        if not name:
            flash("ط·آ·ط¢آ§ط·آ·ط¢آ³ط·آ¸أ¢â‚¬آ¦ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ¸ط·آ¸ط¸آ¾ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ·ط·آ¸أ¢â‚¬â€چط·آ¸ط«â€ ط·آ·ط¢آ¨.", "danger")
        elif min(base_salary, allowances, insurance_employee, insurance_company, tax) < 0:
            flash("ط·آ¸أ¢â‚¬ع‘ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬آ¦ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ¸ط·آ¸ط¸آ¾ ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¦â€™ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ  ط·آ·ط¹آ¾ط·آ¸ط¦â€™ط·آ¸ط«â€ ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ³ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¨ط·آ·ط¢آ©.", "danger")
        else:
            try:
                cur.execute(
                    """
                    INSERT INTO employees(code,name,department,job_title,hire_date,base_salary,allowances,insurance_employee,insurance_company,tax,notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (code, name, department, job_title, hire_date, base_salary, allowances, insurance_employee, insurance_company, tax, notes),
                )
                employee_id = cur.lastrowid
                log_action(cur, "create", "employee", employee_id, name)
                conn.commit()
                conn.close()
                flash("ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬آ¦ط·آ·ط¹آ¾ ط·آ·ط¢آ¥ط·آ·ط¢آ¶ط·آ·ط¢آ§ط·آ¸ط¸آ¾ط·آ·ط¢آ© ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ¸ط·آ¸ط¸آ¾.", "success")
                return redirect(url_for("employees"))
            except sqlite3.IntegrityError:
                flash("ط·آ¸ط¦â€™ط·آ¸ط«â€ ط·آ·ط¢آ¯ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ¸ط·آ¸ط¸آ¾ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ³ط·آ·ط¹آ¾ط·آ·ط¢آ®ط·آ·ط¢آ¯ط·آ¸أ¢â‚¬آ¦ ط·آ·ط¢آ¨ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸ط¸آ¾ط·آ·ط¢آ¹ط·آ¸أ¢â‚¬â€چ.", "danger")
    cur.execute(
        """
        SELECT id,code,name,department,job_title,hire_date,base_salary,allowances,insurance_employee,insurance_company,tax,status
        FROM employees
        ORDER BY id DESC
        """
    )
    rows = cur.fetchall()
    conn.close()
    return render_template("employees.html", rows=rows)


@app.route("/employees/<int:id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("hr", write_always=True)
def edit_employee(id):
    return build_edit_employee_view(MODULE_DEPS)(id)
@app.route("/employees/<int:id>/delete", methods=["POST"])
@login_required
@permission_required("hr", write_always=True)
def delete_employee(id):
    return build_delete_employee_view(MODULE_DEPS)(id)
def _sales_returns_v2():
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
        options = {item["product_id"]: item for item in _invoice_product_options(cur, "sales", invoice_id)}
        lines = []
        for idx, product_id in enumerate(product_ids):
            product_id = int(parse_positive_amount(product_id) or 0)
            quantity = parse_positive_amount(quantities[idx] if idx < len(quantities) else 0)
            option = options.get(product_id)
            if product_id and quantity > 0 and option:
                lines.append((product_id, quantity, option))
        if not date_value or not invoice or not lines:
            flash("ط·آ·ط¢آ±ط·آ·ط¢آ§ط·آ·ط¢آ¬ط·آ·ط¢آ¹ ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ§ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ§ط·آ·ط¹آ¾ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹.", "danger")
        elif any(line[1] > line[2]["available"] for line in lines):
            flash("ط·آ¸ط¸آ¹ط·آ¸ط«â€ ط·آ·ط¢آ¬ط·آ·ط¢آ¯ ط·آ·ط¢آµط·آ¸أ¢â‚¬آ ط·آ¸ط¸آ¾ ط·آ·ط¹آ¾ط·آ·ط¹آ¾ط·آ·ط¢آ¬ط·آ·ط¢آ§ط·آ¸ط«â€ ط·آ·ط¢آ² ط·آ¸ط¦â€™ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¸آ¹ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬طŒ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸ط¦â€™ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¸آ¹ط·آ·ط¢آ© ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ·ط¹آ¾ط·آ·ط¢آ§ط·آ·ط¢آ­ط·آ·ط¢آ© ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯.", "danger")
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
                tax_amount = total * (invoice[2] or DEFAULT_TAX_RATE) / 100
                grand_total = total + tax_amount
                cur.execute("SELECT name,purchase_price FROM products WHERE id=?", (product_id,))
                product = cur.fetchone()
                cost_total = quantity * (product[1] or 0)
                journal_id = create_auto_journal(cur, date_value, f"ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ - {product[0]}", "4200", credit_code, total)
                tax_journal_id = create_auto_journal(cur, date_value, f"ط·آ·ط¢آ¶ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ¨ط·آ·ط¢آ© ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ - {product[0]}", "2200", credit_code, tax_amount) if tax_amount > 0 else None
                cogs_journal_id = create_auto_journal(cur, date_value, f"ط·آ·ط¢آ¹ط·آ¸ط¦â€™ط·آ·ط¢آ³ ط·آ·ط¹آ¾ط·آ¸ط¦â€™ط·آ¸أ¢â‚¬â€چط·آ¸ط¸آ¾ط·آ·ط¢آ© ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ - {product[0]}", "1400", "6100", cost_total) if cost_total > 0 else None
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
                cur.execute("INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes) VALUES (?,?,?,?,?,?,?)", (date_value, product_id, "return_in", quantity, "sales_return", return_id, notes or "ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹"))
                log_action(cur, "create", "sales_return", return_id, f"invoice={invoice_id}; total={grand_total}")
            conn.commit()
            conn.close()
            rebuild_ledger()
            flash("ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬آ¦ ط·آ·ط¹آ¾ط·آ·ط¢آ³ط·آ·ط¢آ¬ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ط·آ·ط¢آ§ط·آ·ط¹آ¾ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ط·آ·ط¢آ§ط·آ·ط¹آ¾.", "success")
            return redirect(url_for("sales_returns"))
    cur.execute("SELECT id,date,grand_total FROM sales_invoices WHERE status='posted' ORDER BY id DESC")
    invoices = cur.fetchall()
    invoice_products = {row[0]: _invoice_product_options(cur, "sales", row[0]) for row in invoices}
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
    return render_template("returns.html", title="ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ط·آ·ط¢آ§ط·آ·ط¹آ¾ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ط·آ·ط¢آ§ط·آ·ط¹آ¾", rows=rows, invoices=invoices, invoice_products_json=json.dumps(invoice_products, ensure_ascii=False), action_url=url_for("sales_returns"), invoice_field="sales_invoice_id")


def _purchase_returns_v2():
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
        options = {item["product_id"]: item for item in _invoice_product_options(cur, "purchase", invoice_id)}
        lines = []
        for idx, product_id in enumerate(product_ids):
            product_id = int(parse_positive_amount(product_id) or 0)
            quantity = parse_positive_amount(quantities[idx] if idx < len(quantities) else 0)
            option = options.get(product_id)
            if product_id and quantity > 0 and option:
                lines.append((product_id, quantity, option))
        if not date_value or not invoice or not lines:
            flash("ط·آ·ط¢آ±ط·آ·ط¢آ§ط·آ·ط¢آ¬ط·آ·ط¢آ¹ ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ§ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ§ط·آ·ط¹آ¾ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ¯.", "danger")
        else:
            for product_id, quantity, option in lines:
                cur.execute("SELECT stock_quantity,name,purchase_price FROM products WHERE id=?", (product_id,))
                product = cur.fetchone()
                if not product or product[0] < quantity or quantity > option["available"]:
                    conn.close()
                    flash("ط·آ·ط¢آ±ط·آ·ط¢آ§ط·آ·ط¢آ¬ط·آ·ط¢آ¹ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸ط¦â€™ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¸آ¹ط·آ·ط¢آ§ط·آ·ط¹آ¾ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ·ط¹آ¾ط·آ·ط¢آ§ط·آ·ط¢آ­ط·آ·ط¢آ© ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ ط·آ·ط¢آ£ط·آ¸ط«â€  ط·آ·ط¢آ±ط·آ·ط¢آµط·آ¸ط¸آ¹ط·آ·ط¢آ¯ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ®ط·آ·ط¢آ²ط·آ¸ط«â€ ط·آ¸أ¢â‚¬آ .", "danger")
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
                tax_amount = total * (invoice[2] or DEFAULT_TAX_RATE) / 100
                grand_total = total + tax_amount
                journal_id = create_auto_journal(cur, date_value, f"ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ´ط·آ·ط¹آ¾ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ§ط·آ·ط¹آ¾ - {product[0]}", debit_code, "1400", total)
                tax_journal_id = create_auto_journal(cur, date_value, f"ط·آ·ط¢آ¶ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ¨ط·آ·ط¢آ© ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ´ط·آ·ط¹آ¾ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ§ط·آ·ط¹آ¾ - {product[0]}", debit_code, "1500", tax_amount) if tax_amount > 0 else None
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
                cur.execute("INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes) VALUES (?,?,?,?,?,?,?)", (date_value, product_id, "return_out", -quantity, "purchase_return", return_id, notes or "ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ´ط·آ·ط¹آ¾ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ§ط·آ·ط¹آ¾"))
                log_action(cur, "create", "purchase_return", return_id, f"invoice={invoice_id}; total={grand_total}")
            conn.commit()
            conn.close()
            rebuild_ledger()
            flash("ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬آ¦ ط·آ·ط¹آ¾ط·آ·ط¢آ³ط·آ·ط¢آ¬ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ط·آ·ط¢آ§ط·آ·ط¹آ¾ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬آ .", "success")
            return redirect(url_for("purchase_returns"))
    cur.execute("SELECT id,date,grand_total FROM purchase_invoices WHERE status='posted' ORDER BY id DESC")
    invoices = cur.fetchall()
    invoice_products = {row[0]: _invoice_product_options(cur, "purchase", row[0]) for row in invoices}
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
    return render_template("returns.html", title="ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ط·آ·ط¢آ§ط·آ·ط¹آ¾ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬آ ", rows=rows, invoices=invoices, invoice_products_json=json.dumps(invoice_products, ensure_ascii=False), action_url=url_for("purchase_returns"), invoice_field="purchase_invoice_id")


def _customer_statement_v2(id):
    conn = db()
    cur = conn.cursor()
    company = get_company_settings(cur)
    cur.execute("SELECT name FROM customers WHERE id=?", (id,))
    customer = cur.fetchone()
    if not customer:
        conn.close()
        flash("ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¹ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ ط·آ·ط·â€؛ط·آ¸ط¸آ¹ط·آ·ط¢آ± ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ¬ط·آ¸ط«â€ ط·آ·ط¢آ¯.", "danger")
        return redirect(url_for("customers"))
    entries = []
    cur.execute("SELECT date,id,grand_total,payment_type,status,cancel_reason FROM sales_invoices WHERE customer_id=? AND status<>'draft'", (id,))
    for date, invoice_id, total, payment_type, status, cancel_reason in cur.fetchall():
        display_status = "ط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ¸أ¢â‚¬آ°" if status == "cancelled" else "ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ­ط·آ¸أ¢â‚¬â€چ"
        suffix = f" - ط·آ·ط¢آ³ط·آ·ط¢آ¨ط·آ·ط¢آ¨ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¥ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ·ط¢آ§ط·آ·ط·إ’: {cancel_reason}" if status == "cancelled" and cancel_reason else ""
        if payment_type == "credit":
            entries.append((date, f"ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ ط·آ·ط¢آ¢ط·آ·ط¢آ¬ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ© #{invoice_id}{suffix}", total, 0, display_status))
            if status == "cancelled":
                entries.append((date, f"ط·آ·ط¢آ¥ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ·ط¢آ§ط·آ·ط·إ’ ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ ط·آ·ط¢آ¢ط·آ·ط¢آ¬ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ© #{invoice_id}", 0, total, "ط·آ·ط¢آ¥ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ·ط¢آ§ط·آ·ط·إ’"))
        else:
            entries.append((date, f"ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ ط·آ¸أ¢â‚¬آ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¯ط·آ¸ط¸آ¹ط·آ·ط¢آ© #{invoice_id}{suffix}", total, 0, display_status))
            entries.append((date, f"ط·آ·ط¹آ¾ط·آ·ط¢آ­ط·آ·ط¢آµط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ ط·آ¸أ¢â‚¬آ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¯ط·آ¸ط¸آ¹ ط·آ¸أ¢â‚¬â€چط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© #{invoice_id}{suffix}", 0, total, display_status))
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
    for date, return_id, total, payment_type, product_name in cur.fetchall():
        if payment_type == "credit":
            entries.append((date, f"ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ط·آ·ط¢آ§ط·آ·ط¹آ¾ #{return_id} - {product_name}", 0, total, "ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ­ط·آ¸أ¢â‚¬â€چ"))
        else:
            entries.append((date, f"ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ط·آ·ط¢آ§ط·آ·ط¹آ¾ ط·آ¸أ¢â‚¬آ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¯ط·آ¸ط¸آ¹ #{return_id} - {product_name}", 0, total, "ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ­ط·آ¸أ¢â‚¬â€چ"))
            entries.append((date, f"ط·آ·ط¢آ±ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬آ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¯ط·آ¸ط¸آ¹ط·آ·ط¢آ© ط·آ·ط¢آ¹ط·آ¸أ¢â‚¬آ  ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ #{return_id}", total, 0, "ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ­ط·آ¸أ¢â‚¬â€چ"))
    cur.execute("SELECT date,id,amount,notes,status,cancel_reason FROM receipt_vouchers WHERE customer_id=? AND status<>'draft'", (id,))
    for date, voucher_id, amount, notes, status, cancel_reason in cur.fetchall():
        display_status = "ط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ¸أ¢â‚¬آ°" if status == "cancelled" else "ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ­ط·آ¸أ¢â‚¬â€چ"
        label = f"ط·آ·ط¢آ³ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¨ط·آ·ط¢آ¶ #{voucher_id}"
        if notes:
            label += f" - {notes}"
        if status == "cancelled" and cancel_reason:
            label += f" - ط·آ·ط¢آ³ط·آ·ط¢آ¨ط·آ·ط¢آ¨ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¥ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ·ط¢آ§ط·آ·ط·إ’: {cancel_reason}"
        entries.append((date, label, 0, amount, display_status))
        if status == "cancelled":
            entries.append((date, f"ط·آ·ط¢آ¥ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ·ط¢آ§ط·آ·ط·إ’ ط·آ·ط¢آ³ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¨ط·آ·ط¢آ¶ #{voucher_id}", amount, 0, "ط·آ·ط¢آ¥ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ·ط¢آ§ط·آ·ط·إ’"))
    entries.sort(key=lambda row: row[0])
    debit = sum(row[2] for row in entries)
    credit = sum(row[3] for row in entries)
    balance = debit - credit
    conn.close()
    return render_template("party_statement.html", title=f"ط·آ¸ط¦â€™ط·آ·ط¢آ´ط·آ¸ط¸آ¾ ط·آ·ط¢آ­ط·آ·ط¢آ³ط·آ·ط¢آ§ط·آ·ط¢آ¨ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¹ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ: {customer[0]}", company=company, party_name=customer[0], party_type="ط·آ·ط¢آ¹ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ", rows=entries, debit=debit, credit=credit, balance=balance, balance_label="ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ¯ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬آ " if balance > 0 else "ط·آ·ط¢آ¯ط·آ·ط¢آ§ط·آ·ط¢آ¦ط·آ¸أ¢â‚¬آ ")


def _supplier_statement_v2(id):
    conn = db()
    cur = conn.cursor()
    company = get_company_settings(cur)
    cur.execute("SELECT name FROM suppliers WHERE id=?", (id,))
    supplier = cur.fetchone()
    if not supplier:
        conn.close()
        flash("ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ¯ ط·آ·ط·â€؛ط·آ¸ط¸آ¹ط·آ·ط¢آ± ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ¬ط·آ¸ط«â€ ط·آ·ط¢آ¯.", "danger")
        return redirect(url_for("suppliers"))
    entries = []
    cur.execute("SELECT date,id,grand_total,payment_type,status,cancel_reason FROM purchase_invoices WHERE supplier_id=? AND status<>'draft'", (id,))
    for date, invoice_id, total, payment_type, status, cancel_reason in cur.fetchall():
        display_status = "ط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ¸أ¢â‚¬آ°" if status == "cancelled" else "ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ­ط·آ¸أ¢â‚¬â€چ"
        suffix = f" - ط·آ·ط¢آ³ط·آ·ط¢آ¨ط·آ·ط¢آ¨ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¥ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ·ط¢آ§ط·آ·ط·إ’: {cancel_reason}" if status == "cancelled" and cancel_reason else ""
        if payment_type == "credit":
            entries.append((date, f"ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ´ط·آ·ط¢آ±ط·آ·ط¢آ§ط·آ·ط·إ’ ط·آ·ط¢آ¢ط·آ·ط¢آ¬ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ© #{invoice_id}{suffix}", 0, total, display_status))
        else:
            entries.append((date, f"ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ´ط·آ·ط¢آ±ط·آ·ط¢آ§ط·آ·ط·إ’ ط·آ¸أ¢â‚¬آ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¯ط·آ¸ط¸آ¹ط·آ·ط¢آ© #{invoice_id}{suffix}", 0, total, display_status))
            entries.append((date, f"ط·آ·ط¢آ³ط·آ·ط¢آ¯ط·آ·ط¢آ§ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬آ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¯ط·آ¸ط¸آ¹ ط·آ¸أ¢â‚¬â€چط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© #{invoice_id}{suffix}", total, 0, display_status))
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
    for date, return_id, total, payment_type, product_name in cur.fetchall():
        if payment_type == "credit":
            entries.append((date, f"ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ´ط·آ·ط¹آ¾ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ§ط·آ·ط¹آ¾ #{return_id} - {product_name}", total, 0, "ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ­ط·آ¸أ¢â‚¬â€چ"))
        else:
            entries.append((date, f"ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ´ط·آ·ط¹آ¾ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ§ط·آ·ط¹آ¾ ط·آ¸أ¢â‚¬آ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¯ط·آ¸ط¸آ¹ #{return_id} - {product_name}", total, 0, "ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ­ط·آ¸أ¢â‚¬â€چ"))
            entries.append((date, f"ط·آ·ط¢آ§ط·آ·ط¢آ³ط·آ·ط¹آ¾ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ·ط¢آ§ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬آ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¯ط·آ¸ط¸آ¹ط·آ·ط¢آ© ط·آ·ط¢آ¹ط·آ¸أ¢â‚¬آ  ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ #{return_id}", 0, total, "ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ­ط·آ¸أ¢â‚¬â€چ"))
    cur.execute("SELECT date,id,amount,notes,status,cancel_reason FROM payment_vouchers WHERE supplier_id=? AND status<>'draft'", (id,))
    for date, voucher_id, amount, notes, status, cancel_reason in cur.fetchall():
        display_status = "ط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ¸أ¢â‚¬آ°" if status == "cancelled" else "ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ­ط·آ¸أ¢â‚¬â€چ"
        label = f"ط·آ·ط¢آ³ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯ ط·آ·ط¢آµط·آ·ط¢آ±ط·آ¸ط¸آ¾ #{voucher_id}"
        if notes:
            label += f" - {notes}"
        if status == "cancelled" and cancel_reason:
            label += f" - ط·آ·ط¢آ³ط·آ·ط¢آ¨ط·آ·ط¢آ¨ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¥ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ·ط¢آ§ط·آ·ط·إ’: {cancel_reason}"
        entries.append((date, label, amount, 0, display_status))
        if status == "cancelled":
            entries.append((date, f"ط·آ·ط¢آ¥ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ·ط¢آ§ط·آ·ط·إ’ ط·آ·ط¢آ³ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯ ط·آ·ط¢آµط·آ·ط¢آ±ط·آ¸ط¸آ¾ #{voucher_id}", 0, amount, "ط·آ·ط¢آ¥ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ·ط¢آ§ط·آ·ط·إ’"))
    entries.sort(key=lambda row: row[0])
    debit = sum(row[2] for row in entries)
    credit = sum(row[3] for row in entries)
    balance = credit - debit
    conn.close()
    return render_template("party_statement.html", title=f"ط·آ¸ط¦â€™ط·آ·ط¢آ´ط·آ¸ط¸آ¾ ط·آ·ط¢آ­ط·آ·ط¢آ³ط·آ·ط¢آ§ط·آ·ط¢آ¨ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ¯: {supplier[0]}", company=company, party_name=supplier[0], party_type="ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ¯", rows=entries, debit=debit, credit=credit, balance=balance, balance_label="ط·آ·ط¢آ¯ط·آ·ط¢آ§ط·آ·ط¢آ¦ط·آ¸أ¢â‚¬آ " if balance > 0 else "ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ¯ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬آ ")


def _print_sale_v2(id):
    conn = db()
    cur = conn.cursor()
    company = get_company_settings(cur)
    cur.execute(
        """
        SELECT s.id,s.date,COALESCE(c.name,'ط·آ·ط¢آ·ط·آ¢ط¢آ¨ط·آ·ط¢آ¸ط·آ¸ط¢آ¹ط·آ·ط¢آ·ط·آ¢ط¢آ¹ ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬ط¢آ ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬ط¹â€کط·آ·ط¢آ·ط·آ¢ط¢آ¯ط·آ·ط¢آ¸ط·آ¸ط¢آ¹'),COALESCE(c.phone,''),COALESCE(c.address,''),
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
        flash("ط·آ·ط¢آ¸ط·آ¸ط¢آ¾ط·آ·ط¢آ·ط·آ¢ط¢آ§ط·آ·ط¢آ·ط·آ¹ط¢آ¾ط·آ·ط¢آ¸ط·آ«أ¢â‚¬آ ط·آ·ط¢آ·ط·آ¢ط¢آ±ط·آ·ط¢آ·ط·آ¢ط¢آ© ط·آ·ط¢آ·ط·آ¢ط¢آ§ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬أ¢â‚¬ع†ط·آ·ط¢آ·ط·آ¢ط¢آ¨ط·آ·ط¢آ¸ط·آ¸ط¢آ¹ط·آ·ط¢آ·ط·آ¢ط¢آ¹ ط·آ·ط¢آ·ط·آ·أ¢â‚¬ط›ط·آ·ط¢آ¸ط·آ¸ط¢آ¹ط·آ·ط¢آ·ط·آ¢ط¢آ± ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬ط¢آ¦ط·آ·ط¢آ¸ط·آ«أ¢â‚¬آ ط·آ·ط¢آ·ط·آ¢ط¢آ¬ط·آ·ط¢آ¸ط·آ«أ¢â‚¬آ ط·آ·ط¢آ·ط·آ¢ط¢آ¯ط·آ·ط¢آ·ط·آ¢ط¢آ©.", "danger")
        return redirect(url_for("sales"))
    return render_template(
        "print_document.html",
        company=company,
        doc=doc,
        doc_type="ط·آ·ط¢آ¸ط·آ¸ط¢آ¾ط·آ·ط¢آ·ط·آ¢ط¢آ§ط·آ·ط¢آ·ط·آ¹ط¢آ¾ط·آ·ط¢آ¸ط·آ«أ¢â‚¬آ ط·آ·ط¢آ·ط·آ¢ط¢آ±ط·آ·ط¢آ·ط·آ¢ط¢آ© ط·آ·ط¢آ·ط·آ¢ط¢آ¨ط·آ·ط¢آ¸ط·آ¸ط¢آ¹ط·آ·ط¢آ·ط·آ¢ط¢آ¹",
        party_label="ط·آ·ط¢آ·ط·آ¢ط¢آ§ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬أ¢â‚¬ع†ط·آ·ط¢آ·ط·آ¢ط¢آ¹ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬ط¢آ¦ط·آ·ط¢آ¸ط·آ¸ط¢آ¹ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬أ¢â‚¬ع†",
        sales_invoice=True,
        amount_in_words=amount_to_words(doc[12]),
    )


def _print_purchase_v2(id):
    conn = db()
    cur = conn.cursor()
    company = get_company_settings(cur)
    cur.execute(
        """
        SELECT p.id,p.date,COALESCE(s.name,'ط·آ·ط¢آ·ط·آ¢ط¢آ´ط·آ·ط¢آ·ط·آ¢ط¢آ±ط·آ·ط¢آ·ط·آ¢ط¢آ§ط·آ·ط¢آ·ط·آ·ط¥â€™ ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬ط¢آ ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬ط¹â€کط·آ·ط¢آ·ط·آ¢ط¢آ¯ط·آ·ط¢آ¸ط·آ¸ط¢آ¹'),COALESCE(s.phone,''),COALESCE(s.address,''),
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
        flash("ط·آ·ط¢آ¸ط·آ¸ط¢آ¾ط·آ·ط¢آ·ط·آ¢ط¢آ§ط·آ·ط¢آ·ط·آ¹ط¢آ¾ط·آ·ط¢آ¸ط·آ«أ¢â‚¬آ ط·آ·ط¢آ·ط·آ¢ط¢آ±ط·آ·ط¢آ·ط·آ¢ط¢آ© ط·آ·ط¢آ·ط·آ¢ط¢آ§ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬أ¢â‚¬ع†ط·آ·ط¢آ·ط·آ¢ط¢آ´ط·آ·ط¢آ·ط·آ¢ط¢آ±ط·آ·ط¢آ·ط·آ¢ط¢آ§ط·آ·ط¢آ·ط·آ·ط¥â€™ ط·آ·ط¢آ·ط·آ·أ¢â‚¬ط›ط·آ·ط¢آ¸ط·آ¸ط¢آ¹ط·آ·ط¢آ·ط·آ¢ط¢آ± ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬ط¢آ¦ط·آ·ط¢آ¸ط·آ«أ¢â‚¬آ ط·آ·ط¢آ·ط·آ¢ط¢آ¬ط·آ·ط¢آ¸ط·آ«أ¢â‚¬آ ط·آ·ط¢آ·ط·آ¢ط¢آ¯ط·آ·ط¢آ·ط·آ¢ط¢آ©.", "danger")
        return redirect(url_for("purchases"))
    return render_template(
        "print_document.html",
        company=company,
        doc=doc,
        doc_type="ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬ط¢آ¦ط·آ·ط¢آ·ط·آ¢ط¢آ³ط·آ·ط¢آ·ط·آ¹ط¢آ¾ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬ط¢آ ط·آ·ط¢آ·ط·آ¢ط¢آ¯ ط·آ·ط¢آ·ط·آ¢ط¢آ¯ط·آ·ط¢آ·ط·آ¢ط¢آ§ط·آ·ط¢آ·ط·آ¢ط¢آ®ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬أ¢â‚¬ع†ط·آ·ط¢آ¸ط·آ¸ط¢آ¹ - ط·آ·ط¢آ·ط·آ¹ط¢آ¾ط·آ·ط¢آ·ط·آ¢ط¢آ³ط·آ·ط¢آ·ط·آ¢ط¢آ¬ط·آ·ط¢آ¸ط·آ¸ط¢آ¹ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬أ¢â‚¬ع† ط·آ·ط¢آ¸ط·آ¸ط¢آ¾ط·آ·ط¢آ·ط·آ¢ط¢آ§ط·آ·ط¢آ·ط·آ¹ط¢آ¾ط·آ·ط¢آ¸ط·آ«أ¢â‚¬آ ط·آ·ط¢آ·ط·آ¢ط¢آ±ط·آ·ط¢آ·ط·آ¢ط¢آ© ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬ط¢آ¦ط·آ·ط¢آ¸ط·آ«أ¢â‚¬آ ط·آ·ط¢آ·ط·آ¢ط¢آ±ط·آ·ط¢آ·ط·آ¢ط¢آ¯",
        party_label="ط·آ·ط¢آ·ط·آ¢ط¢آ§ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬أ¢â‚¬ع†ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬ط¢آ¦ط·آ·ط¢آ¸ط·آ«أ¢â‚¬آ ط·آ·ط¢آ·ط·آ¢ط¢آ±ط·آ·ط¢آ·ط·آ¢ط¢آ¯",
        supplier_invoice=True,
        amount_in_words=amount_to_words(doc[12]),
    )


def _print_receipt_v2(id):
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
        flash("ط·آ·ط¢آ·ط·آ¢ط¢آ³ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬ط¢آ ط·آ·ط¢آ·ط·آ¢ط¢آ¯ ط·آ·ط¢آ·ط·آ¢ط¢آ§ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬أ¢â‚¬ع†ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬ط¹â€کط·آ·ط¢آ·ط·آ¢ط¢آ¨ط·آ·ط¢آ·ط·آ¢ط¢آ¶ ط·آ·ط¢آ·ط·آ·أ¢â‚¬ط›ط·آ·ط¢آ¸ط·آ¸ط¢آ¹ط·آ·ط¢آ·ط·آ¢ط¢آ± ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬ط¢آ¦ط·آ·ط¢آ¸ط·آ«أ¢â‚¬آ ط·آ·ط¢آ·ط·آ¢ط¢آ¬ط·آ·ط¢آ¸ط·آ«أ¢â‚¬آ ط·آ·ط¢آ·ط·آ¢ط¢آ¯.", "danger")
        return redirect(url_for("receipts"))
    return render_template(
        "print_voucher.html",
        company=company,
        doc=doc,
        doc_type="ط·آ·ط¢آ·ط·آ¢ط¢آ³ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬ط¢آ ط·آ·ط¢آ·ط·آ¢ط¢آ¯ ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬ط¹â€کط·آ·ط¢آ·ط·آ¢ط¢آ¨ط·آ·ط¢آ·ط·آ¢ط¢آ¶",
        party_label="ط·آ·ط¢آ·ط·آ¢ط¢آ§ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬أ¢â‚¬ع†ط·آ·ط¢آ·ط·آ¢ط¢آ¹ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬ط¢آ¦ط·آ·ط¢آ¸ط·آ¸ط¢آ¹ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬أ¢â‚¬ع†",
        amount_in_words=amount_to_words(doc[5]),
    )


def _print_payment_v2(id):
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
        flash("ط·آ·ط¢آ·ط·آ¢ط¢آ³ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬ط¢آ ط·آ·ط¢آ·ط·آ¢ط¢آ¯ ط·آ·ط¢آ·ط·آ¢ط¢آ§ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬أ¢â‚¬ع†ط·آ·ط¢آ·ط·آ¢ط¢آµط·آ·ط¢آ·ط·آ¢ط¢آ±ط·آ·ط¢آ¸ط·آ¸ط¢آ¾ ط·آ·ط¢آ·ط·آ·أ¢â‚¬ط›ط·آ·ط¢آ¸ط·آ¸ط¢آ¹ط·آ·ط¢آ·ط·آ¢ط¢آ± ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬ط¢آ¦ط·آ·ط¢آ¸ط·آ«أ¢â‚¬آ ط·آ·ط¢آ·ط·آ¢ط¢آ¬ط·آ·ط¢آ¸ط·آ«أ¢â‚¬آ ط·آ·ط¢آ·ط·آ¢ط¢آ¯.", "danger")
        return redirect(url_for("payments"))
    return render_template(
        "print_voucher.html",
        company=company,
        doc=doc,
        doc_type="ط·آ·ط¢آ·ط·آ¢ط¢آ³ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬ط¢آ ط·آ·ط¢آ·ط·آ¢ط¢آ¯ ط·آ·ط¢آ·ط·آ¢ط¢آµط·آ·ط¢آ·ط·آ¢ط¢آ±ط·آ·ط¢آ¸ط·آ¸ط¢آ¾",
        party_label="ط·آ·ط¢آ·ط·آ¢ط¢آ§ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬أ¢â‚¬ع†ط·آ·ط¢آ¸ط£آ¢أ¢â€ڑآ¬ط¢آ¦ط·آ·ط¢آ¸ط·آ«أ¢â‚¬آ ط·آ·ط¢آ·ط·آ¢ط¢آ±ط·آ·ط¢آ·ط·آ¢ط¢آ¯",
        amount_in_words=amount_to_words(doc[5]),
    )




@app.route("/receipts/<int:id>/print")
@login_required
@permission_required("receipts")
def print_receipt(id):
    return build_print_receipt_view(MODULE_DEPS)(id)
@app.route("/payments/<int:id>/print")
@login_required
@permission_required("payments")
def print_payment(id):
    return build_print_payment_view(MODULE_DEPS)(id)
@app.route("/customers/<int:id>/statement")
@login_required
@permission_required("customers")
def customer_statement(id):
    return build_customer_statement_view(MODULE_DEPS)(id)
@app.route("/suppliers/<int:id>/statement")
@login_required
@permission_required("suppliers")
def supplier_statement(id):
    return build_supplier_statement_view(MODULE_DEPS)(id)
@app.route("/reports/inventory")
@login_required
@permission_required("reports")
def inventory_report():
    return build_inventory_report_view(MODULE_DEPS)()
@app.route("/reports/customers")
@login_required
@permission_required("reports")
def customers_report():
    return build_customers_report_view(MODULE_DEPS)()
@app.route("/reports/suppliers")
@login_required
@permission_required("reports")
def suppliers_report():
    return build_suppliers_report_view(MODULE_DEPS)()
@app.route("/reports/customers/aging")
@login_required
@permission_required("reports")
def customers_aging_report():
    return build_customers_aging_report_view(MODULE_DEPS)()
@app.route("/reports/suppliers/aging")
@login_required
@permission_required("reports")
def suppliers_aging_report():
    return build_suppliers_aging_report_view(MODULE_DEPS)()
@app.route("/reports/balance-sheet")
@login_required
@permission_required("reports")
def balance_sheet_report():
    return build_balance_sheet_report_view(MODULE_DEPS)()


@app.route("/allocations", methods=["GET", "POST"])
@login_required
@permission_required("accounting")
def allocations():
    return build_allocations_view(MODULE_DEPS)()
@app.route("/returns/sales", methods=["GET", "POST"])
@login_required
@permission_required("sales")
def sales_returns():
    return build_sales_returns_view(MODULE_DEPS)()
@app.route("/returns/purchases", methods=["GET", "POST"])
@login_required
@permission_required("purchases")
def purchase_returns():
    return build_purchase_returns_view(MODULE_DEPS)()
@app.route("/reports/cash-flow")
@login_required
@permission_required("reports")
def cash_flow_report():
    return build_cash_flow_report_view(MODULE_DEPS)()


@app.route("/reports/cost-centers")
@login_required
@permission_required("reports")
def cost_center_report():
    return build_cost_center_report_view(MODULE_DEPS)()


@app.route("/opening-balances", methods=["GET", "POST"])
@login_required
@admin_required
def opening_balances():
    return build_opening_balances_view(MODULE_DEPS)()


@app.route("/year-end", methods=["GET", "POST"])
@login_required
@admin_required
def year_end():
    return build_year_end_view(MODULE_DEPS)()


@app.route("/backup", methods=["GET", "POST"])
@login_required
@admin_required
def backup_restore():
    return build_backup_restore_view(MODULE_DEPS)()


@app.route("/reports/profit-loss")
@login_required
@permission_required("reports")
def profit_loss_report():
    return build_profit_loss_report_view(MODULE_DEPS)()


@app.route("/reports/vat")
@login_required
@permission_required("reports")
def vat_report():
    return build_vat_report_view(MODULE_DEPS)()


@app.route("/audit-log")
@login_required
@admin_required
def audit_log():
    return build_audit_log_view(MODULE_DEPS)()


@app.route("/permissions", methods=["GET", "POST"])
@login_required
@admin_required
def permissions():
    return build_permissions_view(MODULE_DEPS)()


@app.route("/users", methods=["GET", "POST"])
@login_required
@admin_required
def users():
    return build_users_view(MODULE_DEPS)()


def _prepare_einvoice_document(cur, document_type, document_id):
    cur.execute(
        """
        SELECT id
        FROM e_invoice_documents
        WHERE document_type=? AND document_id=?
        """,
        (document_type, document_id),
    )
    row = cur.fetchone()
    if row:
        return row[0], False
    cur.execute(
        """
        INSERT INTO e_invoice_documents(document_type,document_id,status)
        VALUES (?,?,'draft')
        """,
        (document_type, document_id),
    )
    return cur.lastrowid, True


def _customers_report_v2():
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT c.id,c.name,
               COALESCE(SUM(CASE WHEN s.payment_type='credit' AND s.status='posted' THEN s.grand_total ELSE 0 END),0)
               + COALESCE((SELECT SUM(f.grand_total) FROM financial_sales_invoices f WHERE f.customer_id=c.id AND f.status='posted' AND f.payment_type='credit'),0)
               + COALESCE((SELECT SUM(CASE WHEN a.adjustment_type='debit' THEN a.grand_total ELSE 0 END) FROM customer_adjustments a WHERE a.customer_id=c.id AND a.status='posted'),0)
               AS invoices,
               COALESCE((SELECT SUM(r.amount) FROM receipt_vouchers r WHERE r.customer_id=c.id AND r.status='posted'),0)
               + COALESCE((SELECT SUM(CASE WHEN a.adjustment_type='credit' THEN a.grand_total ELSE 0 END) FROM customer_adjustments a WHERE a.customer_id=c.id AND a.status='posted'),0)
               AS receipts
        FROM customers c
        LEFT JOIN sales_invoices s ON c.id=s.customer_id
        GROUP BY c.id
        ORDER BY c.name
        """
    )
    rows = []
    for customer_id, name, invoices, receipts in cur.fetchall():
        rows.append((customer_id, name, invoices, receipts, invoices - receipts))
    total_balance = sum(row[4] for row in rows)
    conn.close()
    return render_template("customers_report.html", rows=rows, total_balance=total_balance)


def _customers_aging_report_v2():
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT c.id,c.name,s.date,s.due_date,s.grand_total
        FROM sales_invoices s
        JOIN customers c ON c.id=s.customer_id
        WHERE s.status='posted' AND s.payment_type='credit'
        UNION ALL
        SELECT c.id,c.name,f.date,f.due_date,f.grand_total
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
    return render_template(
        "aging_report.html",
        title="ط·آ·ط¢آ£ط·آ·ط¢آ¹ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ§ط·آ·ط¢آ± ط·آ·ط¢آ¯ط·آ¸ط¸آ¹ط·آ¸ط«â€ ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¹ط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ط·آ·ط·إ’",
        party_label="ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¹ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ",
        statement_endpoint="customer_statement",
        rows=rows,
        totals=totals,
    )


def _customer_statement_v3(id):
    conn = db()
    cur = conn.cursor()
    company = get_company_settings(cur)
    cur.execute("SELECT name FROM customers WHERE id=?", (id,))
    customer = cur.fetchone()
    if not customer:
        conn.close()
        flash("ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¹ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ ط·آ·ط·â€؛ط·آ¸ط¸آ¹ط·آ·ط¢آ± ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ¬ط·آ¸ط«â€ ط·آ·ط¢آ¯.", "danger")
        return redirect(url_for("customers"))

    entries = []

    cur.execute("SELECT date,id,grand_total,payment_type,status,cancel_reason FROM sales_invoices WHERE customer_id=? AND status<>'draft'", (id,))
    for date_value, invoice_id, total, payment_type, status, cancel_reason in cur.fetchall():
        display_status = "ط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ¸أ¢â‚¬آ°" if status == "cancelled" else "ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ­ط·آ¸أ¢â‚¬â€چ"
        suffix = f" - ط·آ·ط¢آ³ط·آ·ط¢آ¨ط·آ·ط¢آ¨ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¥ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ·ط¢آ§ط·آ·ط·إ’: {cancel_reason}" if status == "cancelled" and cancel_reason else ""
        if payment_type == "credit":
            entries.append((date_value, f"ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ ط·آ·ط¢آ¢ط·آ·ط¢آ¬ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ© #{invoice_id}{suffix}", total, 0, display_status))
            if status == "cancelled":
                entries.append((date_value, f"ط·آ·ط¢آ¥ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ·ط¢آ§ط·آ·ط·إ’ ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ ط·آ·ط¢آ¢ط·آ·ط¢آ¬ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ© #{invoice_id}", 0, total, "ط·آ·ط¢آ¥ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ·ط¢آ§ط·آ·ط·إ’"))
        else:
            entries.append((date_value, f"ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ ط·آ¸أ¢â‚¬آ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¯ط·آ¸ط¸آ¹ط·آ·ط¢آ© #{invoice_id}{suffix}", total, 0, display_status))
            entries.append((date_value, f"ط·آ·ط¹آ¾ط·آ·ط¢آ­ط·آ·ط¢آµط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ ط·آ¸أ¢â‚¬آ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¯ط·آ¸ط¸آ¹ ط·آ¸أ¢â‚¬â€چط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© #{invoice_id}{suffix}", 0, total, display_status))

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
            entries.append((date_value, f"ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ط·آ·ط¢آ§ط·آ·ط¹آ¾ #{return_id} - {product_name}", 0, total, "ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ­ط·آ¸أ¢â‚¬â€چ"))
        else:
            entries.append((date_value, f"ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ط·آ·ط¢آ§ط·آ·ط¹آ¾ ط·آ¸أ¢â‚¬آ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¯ط·آ¸ط¸آ¹ #{return_id} - {product_name}", 0, total, "ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ­ط·آ¸أ¢â‚¬â€چ"))
            entries.append((date_value, f"ط·آ·ط¢آ±ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬آ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¯ط·آ¸ط¸آ¹ط·آ·ط¢آ© ط·آ·ط¢آ¹ط·آ¸أ¢â‚¬آ  ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ¯ط·آ¸ط«â€ ط·آ·ط¢آ¯ #{return_id}", total, 0, "ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ­ط·آ¸أ¢â‚¬â€چ"))

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
        display_status = "ط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ¸أ¢â‚¬آ°" if status == "cancelled" else "ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ­ط·آ¸أ¢â‚¬â€چ"
        if adjustment_type == "debit":
            entries.append((date_value, f"ط·آ·ط¹آ¾ط·آ·ط¢آ³ط·آ¸ط«â€ ط·آ¸ط¸آ¹ط·آ·ط¢آ© ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ¯ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ© {doc_no} - {description}", total, 0, display_status))
        else:
            entries.append((date_value, f"ط·آ·ط¹آ¾ط·آ·ط¢آ³ط·آ¸ط«â€ ط·آ¸ط¸آ¹ط·آ·ط¢آ© ط·آ·ط¢آ¯ط·آ·ط¢آ§ط·آ·ط¢آ¦ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ© {doc_no} - {description}", 0, total, display_status))

    cur.execute("SELECT date,id,amount,notes,status,cancel_reason FROM receipt_vouchers WHERE customer_id=? AND status<>'draft'", (id,))
    for date_value, voucher_id, amount, notes, status, cancel_reason in cur.fetchall():
        display_status = "ط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ¸أ¢â‚¬آ°" if status == "cancelled" else "ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ±ط·آ·ط¢آ­ط·آ¸أ¢â‚¬â€چ"
        label = f"ط·آ·ط¢آ³ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¨ط·آ·ط¢آ¶ #{voucher_id}"
        if notes:
            label += f" - {notes}"
        if status == "cancelled" and cancel_reason:
            label += f" - ط·آ·ط¢آ³ط·آ·ط¢آ¨ط·آ·ط¢آ¨ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¥ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ·ط¢آ§ط·آ·ط·إ’: {cancel_reason}"
        entries.append((date_value, label, 0, amount, display_status))
        if status == "cancelled":
            entries.append((date_value, f"ط·آ·ط¢آ¥ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ·ط¢آ§ط·آ·ط·إ’ ط·آ·ط¢آ³ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¨ط·آ·ط¢آ¶ #{voucher_id}", amount, 0, "ط·آ·ط¢آ¥ط·آ¸أ¢â‚¬â€چط·آ·ط·â€؛ط·آ·ط¢آ§ط·آ·ط·إ’"))

    entries.sort(key=lambda row: (row[0], row[1]))
    debit = sum(row[2] for row in entries)
    credit = sum(row[3] for row in entries)
    balance = debit - credit
    conn.close()
    return render_template(
        "party_statement.html",
        title=f"ط·آ¸ط¦â€™ط·آ·ط¢آ´ط·آ¸ط¸آ¾ ط·آ·ط¢آ­ط·آ·ط¢آ³ط·آ·ط¢آ§ط·آ·ط¢آ¨ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¹ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ: {customer[0]}",
        company=company,
        party_name=customer[0],
        party_type="ط·آ·ط¢آ¹ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ",
        rows=entries,
        debit=debit,
        credit=credit,
        balance=balance,
        balance_label="ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ¯ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬آ " if balance > 0 else "ط·آ·ط¢آ¯ط·آ·ط¢آ§ط·آ·ط¢آ¦ط·آ¸أ¢â‚¬آ ",
    )


def _sales_deliveries_v3():
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
            flash("ط·آ·ط¹آ¾ط·آ·ط¢آ§ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ® ط·آ·ط¢آ¥ط·آ·ط¢آ°ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آµط·آ·ط¢آ±ط·آ¸ط¸آ¾ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ·ط·آ¸أ¢â‚¬â€چط·آ¸ط«â€ ط·آ·ط¢آ¨.", "danger")
        elif not order:
            flash("ط·آ·ط¢آ¨ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯ ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ± ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ ط·آ·ط·â€؛ط·آ¸ط¸آ¹ط·آ·ط¢آ± ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ¬ط·آ¸ط«â€ ط·آ·ط¢آ¯.", "danger")
        elif movement_date and order_date and movement_date < order_date:
            flash("ط·آ·ط¹آ¾ط·آ·ط¢آ§ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ® ط·آ·ط¢آ¥ط·آ·ط¢آ°ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آµط·آ·ط¢آ±ط·آ¸ط¸آ¾ ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¦â€™ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ  ط·آ¸ط¸آ¹ط·آ¸ط¦â€™ط·آ¸ط«â€ ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ£ط·آ·ط¢آ³ط·آ·ط¢آ¨ط·آ¸أ¢â‚¬ع‘ ط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬آ  ط·آ·ط¹آ¾ط·آ·ط¢آ§ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ® ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ± ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹.", "danger")
        elif movement_date and planned_delivery_date and movement_date < planned_delivery_date:
            flash("ط·آ·ط¹آ¾ط·آ·ط¢آ§ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ® ط·آ·ط¢آ¥ط·آ·ط¢آ°ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آµط·آ·ط¢آ±ط·آ¸ط¸آ¾ ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¦â€™ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ  ط·آ¸ط¸آ¹ط·آ¸ط¦â€™ط·آ¸ط«â€ ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ£ط·آ·ط¢آ³ط·آ·ط¢آ¨ط·آ¸أ¢â‚¬ع‘ ط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬آ  ط·آ·ط¹آ¾ط·آ·ط¢آ§ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ® ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ¯ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ­ط·آ·ط¢آ¯ط·آ·ط¢آ¯ ط·آ¸ط¸آ¾ط·آ¸ط¸آ¹ ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ± ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹.", "danger")
        elif delivered_quantity <= 0 or delivered_quantity > remaining:
            flash("ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸ط¦â€™ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¸آ¹ط·آ·ط¢آ© ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬آ ط·آ·ط¢آµط·آ·ط¢آ±ط·آ¸ط¸آ¾ط·آ·ط¢آ© ط·آ¸ط¸آ¹ط·آ·ط¢آ¬ط·آ·ط¢آ¨ ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ  ط·آ·ط¹آ¾ط·آ¸ط¦â€™ط·آ¸ط«â€ ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ£ط·آ¸ط¦â€™ط·آ·ط¢آ¨ط·آ·ط¢آ± ط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آµط·آ¸ط¸آ¾ط·آ·ط¢آ± ط·آ¸ط«â€ ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ ط·آ·ط¹آ¾ط·آ·ط¹آ¾ط·آ·ط¢آ¬ط·آ·ط¢آ§ط·آ¸ط«â€ ط·آ·ط¢آ² ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ·ط¹آ¾ط·آ·ط¢آ¨ط·آ¸أ¢â‚¬ع‘ط·آ¸ط¸آ¹.", "danger")
        elif delivered_quantity > order[9]:
            flash("ط·آ·ط¢آ±ط·آ·ط¢آµط·آ¸ط¸آ¹ط·آ·ط¢آ¯ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ®ط·آ·ط¢آ²ط·آ¸ط«â€ ط·آ¸أ¢â‚¬آ  ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ ط·آ¸ط¸آ¹ط·آ¸ط¦â€™ط·آ¸ط¸آ¾ط·آ¸ط¸آ¹ ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¥ط·آ·ط¢آ°ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آµط·آ·ط¢آ±ط·آ¸ط¸آ¾.", "danger")
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
            cogs_journal_id = create_auto_journal(cur, date_value, f"ط·آ·ط¢آ¥ط·آ·ط¢آ°ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آµط·آ·ط¢آ±ط·آ¸ط¸آ¾ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ط·آ·ط¢آ§ط·آ·ط¹آ¾ {delivery_no} - {order[7]}", "6100", "1400", cost_total) if cost_total > 0 else None
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
                (date_value, order[3], "out", -delivered_quantity, "sales_delivery", delivery_id, f"ط·آ·ط¢آ¥ط·آ·ط¢آ°ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آµط·آ·ط¢آ±ط·آ¸ط¸آ¾ {delivery_no}"),
            )
            log_action(cur, "create", "sales_delivery", delivery_id, f"{delivery_no}; total={grand_total}")
            conn.commit()
            conn.close()
            rebuild_ledger()
            flash(f"ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬آ¦ ط·آ·ط¹آ¾ط·آ·ط¢آ³ط·آ·ط¢آ¬ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ ط·آ·ط¢آ¥ط·آ·ط¢آ°ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آµط·آ·ط¢آ±ط·آ¸ط¸آ¾ {delivery_no}.", "success")
            return redirect(url_for("sales_deliveries"))

    cur.execute(
        """
        SELECT sol.id,so.id,so.date,COALESCE(c.name,'ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ ط·آ¸أ¢â‚¬آ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¯ط·آ¸ط¸آ¹'),p.name,sol.quantity,sol.unit_price,
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
        SELECT sd.id,sd.delivery_no,sd.date,sd.sales_order_id,COALESCE(c.name,'ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ ط·آ¸أ¢â‚¬آ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¯ط·آ¸ط¸آ¹'),p.name,
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


def _purchase_receipts_v3():
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
            flash("ط·آ·ط¹آ¾ط·آ·ط¢آ§ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ® ط·آ·ط¢آ¥ط·آ·ط¢آ°ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ط·آ·ط¢آ³ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ط·آ¸أ¢â‚¬آ¦ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ·ط·آ¸أ¢â‚¬â€چط·آ¸ط«â€ ط·آ·ط¢آ¨.", "danger")
        elif not order:
            flash("ط·آ·ط¢آ¨ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯ ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ± ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ´ط·آ·ط¢آ±ط·آ·ط¢آ§ط·آ·ط·إ’ ط·آ·ط·â€؛ط·آ¸ط¸آ¹ط·آ·ط¢آ± ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ¬ط·آ¸ط«â€ ط·آ·ط¢آ¯.", "danger")
        elif movement_date and order_date and movement_date < order_date:
            flash("ط·آ·ط¹آ¾ط·آ·ط¢آ§ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ® ط·آ·ط¢آ¥ط·آ·ط¢آ°ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ط·آ·ط¢آ³ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ط·آ¸أ¢â‚¬آ¦ ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¦â€™ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ  ط·آ¸ط¸آ¹ط·آ¸ط¦â€™ط·آ¸ط«â€ ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ£ط·آ·ط¢آ³ط·آ·ط¢آ¨ط·آ¸أ¢â‚¬ع‘ ط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬آ  ط·آ·ط¹آ¾ط·آ·ط¢آ§ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ® ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ± ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ´ط·آ·ط¢آ±ط·آ·ط¢آ§ط·آ·ط·إ’.", "danger")
        elif movement_date and planned_supply_date and movement_date < planned_supply_date:
            flash("ط·آ·ط¹آ¾ط·آ·ط¢آ§ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ® ط·آ·ط¢آ¥ط·آ·ط¢آ°ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ط·آ·ط¢آ³ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ط·آ¸أ¢â‚¬آ¦ ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¦â€™ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ  ط·آ¸ط¸آ¹ط·آ¸ط¦â€™ط·آ¸ط«â€ ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ£ط·آ·ط¢آ³ط·آ·ط¢آ¨ط·آ¸أ¢â‚¬ع‘ ط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬آ  ط·آ·ط¹آ¾ط·آ·ط¢آ§ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ® ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ¸ط¸آ¹ط·آ·ط¢آ¯ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ­ط·آ·ط¢آ¯ط·آ·ط¢آ¯ ط·آ¸ط¸آ¾ط·آ¸ط¸آ¹ ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ± ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ´ط·آ·ط¢آ±ط·آ·ط¢آ§ط·آ·ط·إ’.", "danger")
        elif received_quantity <= 0 or received_quantity > remaining:
            flash("ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸ط¦â€™ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¸آ¹ط·آ·ط¢آ© ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ³ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ© ط·آ¸ط¸آ¹ط·آ·ط¢آ¬ط·آ·ط¢آ¨ ط·آ·ط¢آ£ط·آ¸أ¢â‚¬آ  ط·آ·ط¹آ¾ط·آ¸ط¦â€™ط·آ¸ط«â€ ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ£ط·آ¸ط¦â€™ط·آ·ط¢آ¨ط·آ·ط¢آ± ط·آ¸أ¢â‚¬آ¦ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آµط·آ¸ط¸آ¾ط·آ·ط¢آ± ط·آ¸ط«â€ ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ ط·آ·ط¹آ¾ط·آ·ط¹آ¾ط·آ·ط¢آ¬ط·آ·ط¢آ§ط·آ¸ط«â€ ط·آ·ط¢آ² ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ·ط¹آ¾ط·آ·ط¢آ¨ط·آ¸أ¢â‚¬ع‘ط·آ¸ط¸آ¹.", "danger")
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
            journal_id = create_auto_journal(cur, date_value, f"ط·آ·ط¢آ¥ط·آ·ط¢آ°ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ§ط·آ·ط¢آ³ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ط·آ¸أ¢â‚¬آ¦ ط·آ¸أ¢â‚¬آ¦ط·آ·ط¢آ®ط·آ·ط¢آ²ط·آ¸أ¢â‚¬آ ط·آ¸ط¸آ¹ {receipt_no} - {order[7]}", "1400", "2150", total)
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
                (date_value, order[3], "in", received_quantity, "purchase_receipt", receipt_id, f"ط·آ·ط¢آ¥ط·آ·ط¢آ°ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ§ط·آ·ط¢آ³ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ط·آ¸أ¢â‚¬آ¦ {receipt_no}"),
            )
            log_action(cur, "create", "purchase_receipt", receipt_id, f"{receipt_no}; total={grand_total}")
            conn.commit()
            conn.close()
            rebuild_ledger()
            flash(f"ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬آ¦ ط·آ·ط¹آ¾ط·آ·ط¢آ³ط·آ·ط¢آ¬ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ ط·آ·ط¢آ¥ط·آ·ط¢آ°ط·آ¸أ¢â‚¬آ  ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ط·آ·ط¢آ³ط·آ·ط¹آ¾ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ§ط·آ¸أ¢â‚¬آ¦ {receipt_no}.", "success")
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


def _print_sale_v3(id):
    conn = db()
    cur = conn.cursor()
    company = get_company_settings(cur)
    cur.execute(
        """
        SELECT s.id,s.date,COALESCE(c.name,'ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ ط·آ¸أ¢â‚¬آ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¯ط·آ¸ط¸آ¹'),COALESCE(c.phone,''),COALESCE(c.address,''),
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
        flash("ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹ ط·آ·ط·â€؛ط·آ¸ط¸آ¹ط·آ·ط¢آ± ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ¬ط·آ¸ط«â€ ط·آ·ط¢آ¯ط·آ·ط¢آ©.", "danger")
        return redirect(url_for("sales"))
    return render_template(
        "print_document.html",
        company=company,
        doc=doc,
        doc_type="ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ¨ط·آ¸ط¸آ¹ط·آ·ط¢آ¹",
        party_label="ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¹ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ",
        sales_invoice=True,
        amount_in_words=amount_to_words(doc[12]),
    )


def _print_purchase_v3(id):
    conn = db()
    cur = conn.cursor()
    company = get_company_settings(cur)
    cur.execute(
        """
        SELECT p.id,p.date,COALESCE(s.name,'ط·آ·ط¢آ´ط·آ·ط¢آ±ط·آ·ط¢آ§ط·آ·ط·إ’ ط·آ¸أ¢â‚¬آ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¯ط·آ¸ط¸آ¹'),COALESCE(s.phone,''),COALESCE(s.address,''),
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
        flash("ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ´ط·آ·ط¢آ±ط·آ·ط¢آ§ط·آ·ط·إ’ ط·آ·ط·â€؛ط·آ¸ط¸آ¹ط·آ·ط¢آ± ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ¬ط·آ¸ط«â€ ط·آ·ط¢آ¯ط·آ·ط¢آ©.", "danger")
        return redirect(url_for("purchases"))
    return render_template(
        "print_document.html",
        company=company,
        doc=doc,
        doc_type="ط·آ·ط¹آ¾ط·آ·ط¢آ³ط·آ·ط¢آ¬ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ ط·آ¸ط¸آ¾ط·آ·ط¢آ§ط·آ·ط¹آ¾ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ© ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ¯",
        party_label="ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ¯",
        supplier_invoice=True,
        amount_in_words=amount_to_words(doc[12]),
    )


def _print_receipt_v3(id):
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
        flash("ط·آ·ط¢آ³ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¨ط·آ·ط¢آ¶ ط·آ·ط·â€؛ط·آ¸ط¸آ¹ط·آ·ط¢آ± ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ¬ط·آ¸ط«â€ ط·آ·ط¢آ¯.", "danger")
        return redirect(url_for("receipts"))
    return render_template(
        "print_voucher.html",
        company=company,
        doc=doc,
        doc_type="ط·آ·ط¢آ³ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯ ط·آ¸أ¢â‚¬ع‘ط·آ·ط¢آ¨ط·آ·ط¢آ¶",
        party_label="ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آ¹ط·آ¸أ¢â‚¬آ¦ط·آ¸ط¸آ¹ط·آ¸أ¢â‚¬â€چ",
        amount_in_words=amount_to_words(doc[5]),
    )


def _print_payment_v3(id):
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
        flash("ط·آ·ط¢آ³ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯ ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ·ط¢آµط·آ·ط¢آ±ط·آ¸ط¸آ¾ ط·آ·ط·â€؛ط·آ¸ط¸آ¹ط·آ·ط¢آ± ط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ¬ط·آ¸ط«â€ ط·آ·ط¢آ¯.", "danger")
        return redirect(url_for("payments"))
    return render_template(
        "print_voucher.html",
        company=company,
        doc=doc,
        doc_type="ط·آ·ط¢آ³ط·آ¸أ¢â‚¬آ ط·آ·ط¢آ¯ ط·آ·ط¢آµط·آ·ط¢آ±ط·آ¸ط¸آ¾",
        party_label="ط·آ·ط¢آ§ط·آ¸أ¢â‚¬â€چط·آ¸أ¢â‚¬آ¦ط·آ¸ط«â€ ط·آ·ط¢آ±ط·آ·ط¢آ¯",
        amount_in_words=amount_to_words(doc[5]),
    )


@app.route("/credit-notes/sales", methods=["GET", "POST"])
@login_required
@permission_required("sales")
def sales_credit_notes():
    return build_sales_credit_notes_view(MODULE_DEPS)()
@app.route("/credit-notes/sales/<int:id>/print")
@login_required
@permission_required("sales")
def print_sales_credit_note(id):
    return build_print_sales_credit_note_view(MODULE_DEPS)(id)
@app.route("/credit-notes/sales/<int:id>/prepare-einvoice", methods=["POST"])
@login_required
@permission_required("e_invoices", write_always=True)
def prepare_sales_credit_note_einvoice(id):
    return build_prepare_sales_credit_note_einvoice_view(MODULE_DEPS)(id)
@app.route("/debit-notes/suppliers", methods=["GET", "POST"])
@login_required
@permission_required("purchases")
def supplier_debit_notes():
    return build_supplier_debit_notes_view(MODULE_DEPS)()
@app.route("/debit-notes/suppliers/<int:id>/print")
@login_required
@permission_required("purchases")
def print_supplier_debit_note(id):
    return build_print_supplier_debit_note_view(MODULE_DEPS)(id)
@app.route("/adjustments/customers", methods=["GET", "POST"])
@login_required
@permission_required("accounting")
def customer_adjustments():
    return build_customer_adjustments_view(MODULE_DEPS)()
@app.route("/adjustments/customers/<int:id>/print")
@login_required
@permission_required("accounting")
def print_customer_adjustment(id):
    return build_print_customer_adjustment_view(MODULE_DEPS)(id)
@app.route("/adjustments/customers/<int:id>/prepare-einvoice", methods=["POST"])
@login_required
@permission_required("e_invoices", write_always=True)
def prepare_customer_adjustment_einvoice(id):
    return build_prepare_customer_adjustment_einvoice_view(MODULE_DEPS)(id)
@app.route("/e-invoices")
@login_required
@permission_required("e_invoices")
def e_invoices():
    return build_einvoices_view(MODULE_DEPS)()
@app.route("/e-invoices/prepare-sales", methods=["POST"])
@login_required
@permission_required("e_invoices", write_always=True)
def prepare_sales_e_invoices():
    return build_prepare_sales_einvoices_view(MODULE_DEPS)()


# The route functions above remain in place during the modularization phase so
# Flask keeps the original endpoint registration. Runtime dispatch is rebound
# below to the modularized implementations.
MODULE_DEPS = {
    "BASE_DIR": BASE_DIR,
    "DB_PATH": DB_PATH,
    "UPLOAD_DIR": UPLOAD_DIR,
    "db": db,
    "csv_response": csv_response,
    "excel_response": excel_response,
    "log_action": log_action,
    "build_aging_rows": build_aging_rows,
    "row_snapshot": row_snapshot,
    "parse_positive_amount": parse_positive_amount,
    "generate_password_hash": generate_password_hash,
    "get_company_settings": get_company_settings,
    "get_account_id": get_account_id,
    "amount_to_words": amount_to_words,
    "ensure_open_period": ensure_open_period,
    "ensure_posting_rows": ensure_posting_rows,
    "next_document_number": next_document_number,
    "prepare_einvoice_document": _prepare_einvoice_document,
    "parse_iso_date": parse_iso_date,
    "DEFAULT_TAX_RATE": DEFAULT_TAX_RATE,
    "LOGO_EXTENSIONS": LOGO_EXTENSIONS,
    "MAX_LOGO_SIZE": MAX_LOGO_SIZE,
    "ACCOUNT_TYPES": ACCOUNT_TYPES,
    "PERMISSION_MODULES": PERMISSION_MODULES,
    "POSTING_GROUPS": POSTING_GROUPS,
    "create_auto_journal": create_auto_journal,
    "mark_journal_source": mark_journal_source,
    "post_group": post_group,
    "rebuild_ledger": rebuild_ledger,
    "is_group_posted": is_group_posted,
    "reverse_journal": reverse_journal,
    "unpost_group": unpost_group,
    "validate_account_form": validate_account_form,
    "validate_journal_form": validate_journal_form,
}


app.view_functions["dashboard"] = login_required(build_dashboard_view(MODULE_DEPS))
app.view_functions["company_settings"] = login_required(admin_required(build_company_settings_view(MODULE_DEPS)))
app.view_functions["posting_control"] = login_required(admin_required(build_posting_control_view(MODULE_DEPS)))
app.view_functions["posting_control_action"] = login_required(admin_required(build_posting_control_action_view(MODULE_DEPS)))
app.view_functions["fiscal_periods"] = login_required(admin_required(build_fiscal_periods_view(MODULE_DEPS)))
app.view_functions["fiscal_period_action"] = login_required(admin_required(build_fiscal_period_action_view(MODULE_DEPS)))
app.view_functions["accounts"] = login_required(permission_required("accounting")(build_accounts_view(MODULE_DEPS)))
app.view_functions["account_edit"] = login_required(permission_required("accounting", write_always=True)(build_account_edit_view(MODULE_DEPS)))
app.view_functions["account_delete"] = login_required(permission_required("accounting", write_always=True)(build_account_delete_view(MODULE_DEPS)))
app.view_functions["journal"] = login_required(permission_required("accounting")(build_journal_view(MODULE_DEPS)))
app.view_functions["journal_export"] = login_required(permission_required("accounting")(build_journal_export_view(MODULE_DEPS)))
app.view_functions["edit"] = login_required(permission_required("accounting", write_always=True)(build_edit_journal_view(MODULE_DEPS)))
app.view_functions["delete"] = login_required(permission_required("accounting", write_always=True)(build_delete_journal_view(MODULE_DEPS)))
app.view_functions["ledger"] = login_required(permission_required("accounting")(build_ledger_view(MODULE_DEPS)))
app.view_functions["ledger_export"] = login_required(permission_required("accounting")(build_ledger_export_view(MODULE_DEPS)))
app.view_functions["trial"] = login_required(permission_required("accounting")(build_trial_view(MODULE_DEPS)))
app.view_functions["trial_export"] = login_required(permission_required("accounting")(build_trial_export_view(MODULE_DEPS)))
app.view_functions["customers"] = login_required(permission_required("customers")(build_customers_view(MODULE_DEPS)))
app.view_functions["edit_customer"] = login_required(permission_required("customers", write_always=True)(lambda id: build_party_edit_view(MODULE_DEPS)("customers", "العميل", id)))
app.view_functions["delete_customer"] = login_required(permission_required("customers", write_always=True)(lambda id: build_party_delete_view(MODULE_DEPS)("customers", "العميل", id)))
app.view_functions["suppliers"] = login_required(permission_required("suppliers")(build_suppliers_view(MODULE_DEPS)))
app.view_functions["edit_supplier"] = login_required(permission_required("suppliers", write_always=True)(lambda id: build_party_edit_view(MODULE_DEPS)("suppliers", "المورد", id)))
app.view_functions["delete_supplier"] = login_required(permission_required("suppliers", write_always=True)(lambda id: build_party_delete_view(MODULE_DEPS)("suppliers", "المورد", id)))
app.view_functions["products"] = login_required(permission_required("inventory")(build_products_view(MODULE_DEPS)))
app.view_functions["edit_product"] = login_required(permission_required("inventory", write_always=True)(build_edit_product_view(MODULE_DEPS)))
app.view_functions["delete_product"] = login_required(permission_required("inventory", write_always=True)(build_delete_product_view(MODULE_DEPS)))
app.view_functions["inventory"] = login_required(permission_required("inventory")(build_inventory_view(MODULE_DEPS)))
app.view_functions["inventory_report"] = login_required(permission_required("reports")(build_inventory_report_view(MODULE_DEPS)))
app.view_functions["customer_statement"] = login_required(permission_required("customers")(build_customer_statement_view(MODULE_DEPS)))
app.view_functions["supplier_statement"] = login_required(permission_required("suppliers")(build_supplier_statement_view(MODULE_DEPS)))
app.view_functions["sales"] = login_required(permission_required("sales")(build_sales_view(MODULE_DEPS)))
app.view_functions["print_sale"] = login_required(permission_required("sales")(build_print_sale_view(MODULE_DEPS)))
app.view_functions["sales_invoice_from_delivery"] = login_required(permission_required("sales")(build_sales_invoice_from_delivery_view(MODULE_DEPS)))
app.view_functions["financial_sales"] = login_required(permission_required("sales")(build_financial_sales_view(MODULE_DEPS)))
app.view_functions["cancel_sale"] = login_required(permission_required("sales", write_always=True)(build_cancel_sale_view(MODULE_DEPS)))
app.view_functions["edit_sale_invoice"] = login_required(permission_required("sales", write_always=True)(build_edit_sale_invoice_view(MODULE_DEPS)))
app.view_functions["purchases"] = login_required(permission_required("purchases")(build_purchases_view(MODULE_DEPS)))
app.view_functions["purchase_invoice_from_receipt"] = login_required(permission_required("purchases")(build_purchase_invoice_from_receipt_view(MODULE_DEPS)))
if "purchases_multi" in app.view_functions:
    app.view_functions["purchases_multi"] = login_required(permission_required("purchases")(lambda: redirect(url_for("purchases"))))
app.view_functions["cancel_purchase"] = login_required(permission_required("purchases", write_always=True)(build_cancel_purchase_view(MODULE_DEPS)))
app.view_functions["edit_purchase_invoice"] = login_required(permission_required("purchases", write_always=True)(build_edit_purchase_invoice_view(MODULE_DEPS)))
app.view_functions["receipts"] = login_required(permission_required("receipts")(build_receipts_view(MODULE_DEPS)))
app.view_functions["payments"] = login_required(permission_required("payments")(build_payments_view(MODULE_DEPS)))
app.view_functions["print_receipt"] = login_required(permission_required("receipts")(build_print_receipt_view(MODULE_DEPS)))
app.view_functions["print_payment"] = login_required(permission_required("payments")(build_print_payment_view(MODULE_DEPS)))
app.view_functions["cancel_receipt"] = login_required(permission_required("receipts", write_always=True)(build_cancel_receipt_view(MODULE_DEPS)))
app.view_functions["edit_receipt"] = login_required(permission_required("receipts", write_always=True)(build_edit_receipt_view(MODULE_DEPS)))
app.view_functions["cancel_payment"] = login_required(permission_required("payments", write_always=True)(build_cancel_payment_view(MODULE_DEPS)))
app.view_functions["edit_payment"] = login_required(permission_required("payments", write_always=True)(build_edit_payment_view(MODULE_DEPS)))
app.view_functions["customer_adjustments"] = login_required(permission_required("accounting")(build_customer_adjustments_view(MODULE_DEPS)))
app.view_functions["print_customer_adjustment"] = login_required(permission_required("accounting")(build_print_customer_adjustment_view(MODULE_DEPS)))
app.view_functions["prepare_customer_adjustment_einvoice"] = login_required(
    permission_required("e_invoices", write_always=True)(build_prepare_customer_adjustment_einvoice_view(MODULE_DEPS))
)
app.view_functions["allocations"] = login_required(permission_required("accounting")(build_allocations_view(MODULE_DEPS)))
app.view_functions["print_purchase"] = login_required(permission_required("purchases")(build_print_purchase_view(MODULE_DEPS)))
app.view_functions["sales_credit_notes"] = login_required(permission_required("sales")(build_sales_credit_notes_view(MODULE_DEPS)))
app.view_functions["print_sales_credit_note"] = login_required(permission_required("sales")(build_print_sales_credit_note_view(MODULE_DEPS)))
app.view_functions["supplier_debit_notes"] = login_required(permission_required("purchases")(build_supplier_debit_notes_view(MODULE_DEPS)))
app.view_functions["print_supplier_debit_note"] = login_required(permission_required("purchases")(build_print_supplier_debit_note_view(MODULE_DEPS)))
app.view_functions["prepare_sales_credit_note_einvoice"] = login_required(
    permission_required("e_invoices", write_always=True)(build_prepare_sales_credit_note_einvoice_view(MODULE_DEPS))
)
app.view_functions["customers_report"] = login_required(permission_required("reports")(build_customers_report_view(MODULE_DEPS)))
app.view_functions["suppliers_report"] = login_required(permission_required("reports")(build_suppliers_report_view(MODULE_DEPS)))
app.view_functions["customers_aging_report"] = login_required(permission_required("reports")(build_customers_aging_report_view(MODULE_DEPS)))
app.view_functions["suppliers_aging_report"] = login_required(permission_required("reports")(build_suppliers_aging_report_view(MODULE_DEPS)))
app.view_functions["e_invoices"] = login_required(permission_required("e_invoices")(build_einvoices_view(MODULE_DEPS)))
app.view_functions["prepare_sales_e_invoices"] = login_required(
    permission_required("e_invoices", write_always=True)(build_prepare_sales_einvoices_view(MODULE_DEPS))
)
app.view_functions["sales_orders"] = login_required(permission_required("sales")(build_sales_orders_view(MODULE_DEPS)))
app.view_functions["purchase_orders"] = login_required(permission_required("purchases")(build_purchase_orders_view(MODULE_DEPS)))
app.view_functions["sales_deliveries"] = login_required(permission_required("sales")(build_sales_deliveries_view(MODULE_DEPS)))
app.view_functions["purchase_receipts"] = login_required(permission_required("purchases")(build_purchase_receipts_view(MODULE_DEPS)))
app.view_functions["print_purchase_order"] = login_required(permission_required("purchases")(build_print_purchase_order_view(MODULE_DEPS)))
app.view_functions["employees"] = login_required(permission_required("hr")(build_employees_view(MODULE_DEPS)))
app.view_functions["toggle_employee"] = login_required(permission_required("hr", write_always=True)(build_toggle_employee_view(MODULE_DEPS)))
app.view_functions["edit_employee"] = login_required(permission_required("hr", write_always=True)(build_edit_employee_view(MODULE_DEPS)))
app.view_functions["delete_employee"] = login_required(permission_required("hr", write_always=True)(build_delete_employee_view(MODULE_DEPS)))
app.view_functions["payroll"] = login_required(permission_required("hr")(build_payroll_view(MODULE_DEPS)))
app.view_functions["payroll_details"] = login_required(permission_required("hr")(build_payroll_details_view(MODULE_DEPS)))
app.view_functions["sales_returns"] = login_required(permission_required("sales")(build_sales_returns_view(MODULE_DEPS)))
app.view_functions["purchase_returns"] = login_required(permission_required("purchases")(build_purchase_returns_view(MODULE_DEPS)))
app.view_functions["balance_sheet_report"] = login_required(permission_required("reports")(build_balance_sheet_report_view(MODULE_DEPS)))
app.view_functions["cash_flow_report"] = login_required(permission_required("reports")(build_cash_flow_report_view(MODULE_DEPS)))
app.view_functions["cost_center_report"] = login_required(permission_required("reports")(build_cost_center_report_view(MODULE_DEPS)))
app.view_functions["opening_balances"] = login_required(permission_required("accounting", write_always=True)(build_opening_balances_view(MODULE_DEPS)))
app.view_functions["year_end"] = login_required(permission_required("accounting", write_always=True)(build_year_end_view(MODULE_DEPS)))
app.view_functions["profit_loss_report"] = login_required(permission_required("reports")(build_profit_loss_report_view(MODULE_DEPS)))
app.view_functions["vat_report"] = login_required(permission_required("reports")(build_vat_report_view(MODULE_DEPS)))
app.view_functions["backup_restore"] = login_required(admin_required(build_backup_restore_view(MODULE_DEPS)))
app.view_functions["audit_log"] = login_required(admin_required(build_audit_log_view(MODULE_DEPS)))
app.view_functions["permissions"] = login_required(admin_required(build_permissions_view(MODULE_DEPS)))
app.view_functions["users"] = login_required(admin_required(build_users_view(MODULE_DEPS)))

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")

