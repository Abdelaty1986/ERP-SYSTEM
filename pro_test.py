"""
ERP ULTIMATE WORKFLOW TEST V2
=============================

Run:
    python erp_ultimate_workflow_test_v2.py

Use only on a COPY of the project/database.

Improvements over V1:
- Generates unique test codes every run using timestamp.
- Does not continue dynamic tests if seeding test data fails.
- Handles repeated runs better.
- Creates demo customer/supplier/product/invoices/receipts/payments.
"""

import os
import re
import sqlite3
import traceback
from datetime import datetime, date
from werkzeug.security import generate_password_hash

from app import app, DB_PATH


TEST_USERNAME = os.environ.get("ERP_TEST_USER", "hany")
TEST_PASSWORD = os.environ.get("ERP_TEST_PASSWORD", "1986")
TEMPLATES_DIR = "templates"
LOGIN_URL = "/login"

TODAY = date.today().isoformat()
RUN_ID = datetime.now().strftime("%Y%m%d%H%M%S")
TEST_TAG = f"ULTIMATE_TEST_{RUN_ID}"

ALLOWED_REDIRECTS = {
    "/",
    "/purchases/multi",
    "/dev/run-migrations",
    "/dev/run-test",
    "/dev/deploy",
    "/dev/import-data",
    "/dev/backup-now",
}

SKIP_URLS = {
    "/logout",
}

SKIP_ENDPOINTS = {
    "static",
}

REQUIRED_TABLES = {
    "users",
    "accounts",
    "journal",
    "ledger",
    "customers",
    "suppliers",
    "products",
    "sales_invoices",
    "purchase_invoices",
    "sales_invoice_lines",
    "purchase_invoice_lines",
    "receipt_vouchers",
    "payment_vouchers",
    "company_settings",
    "role_permissions",
}

REQUIRED_COLUMNS = {
    "users": {"id", "username", "password", "role"},
    "customers": {"id", "name"},
    "suppliers": {"id", "name"},
    "products": {"id", "name", "stock_quantity"},
    "sales_invoices": {"id", "date", "total", "tax_amount", "withholding_amount", "status"},
    "purchase_invoices": {"id", "date", "total", "tax_amount", "withholding_amount", "status"},
    "sales_invoice_lines": {"invoice_id", "product_id", "total"},
    "purchase_invoice_lines": {"invoice_id", "product_id", "total"},
}

CREATED = {}
SEED_OK = False


def log_ok(msg):
    print("✅", msg)


def log_warn(msg):
    print("⚠️ ", msg)


def log_err(msg):
    print("❌", msg)


def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def table_exists(cur, table):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def columns(cur, table):
    if not table_exists(cur, table):
        return set()
    cur.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def insert_flexible(cur, table, data):
    cols = columns(cur, table)
    payload = {k: v for k, v in data.items() if k in cols}

    if not payload:
        raise RuntimeError(f"No matching columns to insert into {table}")

    keys = list(payload.keys())
    placeholders = ",".join(["?"] * len(keys))
    sql = f"INSERT INTO {table} ({','.join(keys)}) VALUES ({placeholders})"
    cur.execute(sql, [payload[k] for k in keys])
    return cur.lastrowid


def update_if_col(cur, table, row_id, updates):
    cols = columns(cur, table)
    payload = {k: v for k, v in updates.items() if k in cols}
    if not payload:
        return
    sets = ", ".join([f"{k}=?" for k in payload])
    cur.execute(f"UPDATE {table} SET {sets} WHERE id=?", [*payload.values(), row_id])


def ensure_user(cur):
    if not table_exists(cur, "users"):
        return

    cur.execute("SELECT id FROM users WHERE username=?", (TEST_USERNAME,))
    row = cur.fetchone()
    password_hash = generate_password_hash(TEST_PASSWORD)

    if row:
        update_if_col(cur, "users", row[0], {"password": password_hash, "role": "admin"})
        CREATED["user_id"] = row[0]
    else:
        CREATED["user_id"] = insert_flexible(cur, "users", {
            "username": TEST_USERNAME,
            "password": password_hash,
            "role": "admin",
        })


def ensure_min_accounts(cur):
    if not table_exists(cur, "accounts"):
        return

    cols = columns(cur, "accounts")
    samples = [
        ("1100", "الصندوق"),
        ("1300", "العملاء"),
        ("1400", "المخزون"),
        ("1500", "ضريبة مدخلات"),
        ("1510", "خصم وإضافة عملاء"),
        ("2100", "الموردون"),
        ("2200", "ضريبة مخرجات"),
        ("2230", "خصم وإضافة موردين"),
        ("4100", "إيرادات المبيعات"),
        ("6100", "تكلفة البضاعة المباعة"),
    ]

    for code, name in samples:
        if "code" in cols:
            cur.execute("SELECT id FROM accounts WHERE code=?", (code,))
            if cur.fetchone():
                continue

        data = {
            "code": code,
            "name": name,
            "type": "أصول" if code.startswith("1") else ("خصوم" if code.startswith("2") else ("إيرادات" if code.startswith("4") else "مصروفات")),
        }
        try:
            insert_flexible(cur, "accounts", data)
        except sqlite3.Error:
            pass


def seed_data():
    global SEED_OK

    print("\n" + "=" * 60)
    print("4) CREATE TEST DATA")
    print("=" * 60)

    conn = connect_db()
    cur = conn.cursor()

    try:
        ensure_user(cur)
        ensure_min_accounts(cur)

        if table_exists(cur, "customers"):
            customer_id = insert_flexible(cur, "customers", {
                "name": f"عميل اختبار {TEST_TAG}",
                "phone": "01000000000",
                "address": "عنوان اختبار",
                "tax_registration_number": "123456789",
                "tax_id": "123456789",
                "tax_card_number": "123456789",
                "commercial_register": f"CR-{RUN_ID}",
                "contact_person": "مسؤول اختبار",
                "email": "test@example.com",
            })
            CREATED["customer_id"] = customer_id
            log_ok(f"Created customer #{customer_id}")

        if table_exists(cur, "suppliers"):
            supplier_id = insert_flexible(cur, "suppliers", {
                "name": f"مورد اختبار {TEST_TAG}",
                "phone": "01000000001",
                "address": "عنوان مورد اختبار",
                "tax_registration_number": "987654321",
                "tax_id": "987654321",
                "tax_card_number": "987654321",
                "commercial_register": f"SUP-{RUN_ID}",
                "contact_person": "مسؤول مورد",
                "email": "supplier@example.com",
            })
            CREATED["supplier_id"] = supplier_id
            log_ok(f"Created supplier #{supplier_id}")

        if table_exists(cur, "products"):
            product_id = insert_flexible(cur, "products", {
                "name": f"صنف اختبار {TEST_TAG}",
                "code": f"TST-{RUN_ID}",
                "barcode": f"BAR{RUN_ID}",
                "unit": "قطعة",
                "purchase_price": 100,
                "sale_price": 150,
                "stock_quantity": 100,
                "min_stock": 1,
                "description": "صنف تجريبي لاختبار النظام",
            })
            CREATED["product_id"] = product_id
            log_ok(f"Created product #{product_id}")

        customer_id = CREATED.get("customer_id")
        supplier_id = CREATED.get("supplier_id")
        product_id = CREATED.get("product_id")

        if table_exists(cur, "sales_invoices") and product_id:
            sale_id = insert_flexible(cur, "sales_invoices", {
                "date": TODAY,
                "doc_no": f"SI-TEST-{RUN_ID}",
                "customer_id": customer_id,
                "product_id": product_id,
                "quantity": 2,
                "unit_price": 150,
                "total": 300,
                "tax_amount": 42,
                "withholding_amount": 3,
                "payment_type": "cash",
                "status": "draft",
                "notes": TEST_TAG,
            })
            CREATED["sale_id"] = sale_id
            log_ok(f"Created sales invoice #{sale_id}")

            if table_exists(cur, "sales_invoice_lines"):
                line_id = insert_flexible(cur, "sales_invoice_lines", {
                    "invoice_id": sale_id,
                    "product_id": product_id,
                    "quantity": 2,
                    "unit_price": 150,
                    "total": 300,
                    "vat_enabled": 1,
                    "withholding_enabled": 1,
                    "vat_rate": 14,
                    "withholding_rate": 1,
                    "vat_amount": 42,
                    "withholding_amount": 3,
                    "grand_total": 339,
                })
                CREATED["sale_line_id"] = line_id
                log_ok(f"Created sales line #{line_id}")

        if table_exists(cur, "purchase_invoices") and product_id:
            purchase_id = insert_flexible(cur, "purchase_invoices", {
                "date": TODAY,
                "doc_no": f"PI-TEST-{RUN_ID}",
                "supplier_invoice_no": f"SUP-INV-{RUN_ID}",
                "supplier_id": supplier_id,
                "product_id": product_id,
                "quantity": 3,
                "unit_price": 100,
                "total": 300,
                "tax_amount": 42,
                "withholding_amount": 3,
                "payment_type": "cash",
                "status": "draft",
                "notes": TEST_TAG,
            })
            CREATED["purchase_id"] = purchase_id
            log_ok(f"Created purchase invoice #{purchase_id}")

            if table_exists(cur, "purchase_invoice_lines"):
                line_id = insert_flexible(cur, "purchase_invoice_lines", {
                    "invoice_id": purchase_id,
                    "product_id": product_id,
                    "quantity": 3,
                    "unit_price": 100,
                    "total": 300,
                    "vat_enabled": 1,
                    "withholding_enabled": 1,
                    "vat_rate": 14,
                    "withholding_rate": 1,
                    "vat_amount": 42,
                    "withholding_amount": 3,
                    "grand_total": 339,
                })
                CREATED["purchase_line_id"] = line_id
                log_ok(f"Created purchase line #{line_id}")

        if table_exists(cur, "receipt_vouchers") and customer_id:
            receipt_id = insert_flexible(cur, "receipt_vouchers", {
                "date": TODAY,
                "customer_id": customer_id,
                "amount": 100,
                "payment_method": "cash",
                "status": "draft",
                "notes": TEST_TAG,
            })
            CREATED["receipt_id"] = receipt_id
            log_ok(f"Created receipt #{receipt_id}")

        if table_exists(cur, "payment_vouchers") and supplier_id:
            payment_id = insert_flexible(cur, "payment_vouchers", {
                "date": TODAY,
                "supplier_id": supplier_id,
                "amount": 100,
                "payment_method": "cash",
                "status": "draft",
                "notes": TEST_TAG,
            })
            CREATED["payment_id"] = payment_id
            log_ok(f"Created payment #{payment_id}")

        conn.commit()
        SEED_OK = True
        log_ok("Test data committed successfully")

    except Exception:
        conn.rollback()
        CREATED.clear()
        SEED_OK = False
        raise

    finally:
        conn.close()


def collect_template_endpoints():
    endpoints = set()
    pattern = re.compile(r"url_for\(['\"]([^'\"]+)['\"]")
    if not os.path.isdir(TEMPLATES_DIR):
        return endpoints

    for root, dirs, files in os.walk(TEMPLATES_DIR):
        for file in files:
            if file.endswith((".html", ".jinja", ".jinja2")):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    endpoints.update(pattern.findall(f.read()))
    return endpoints


def login(client):
    response = client.post(
        LOGIN_URL,
        data={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        follow_redirects=False,
    )
    with client.session_transaction() as sess:
        if "user_id" in sess:
            return True, "Login OK"
    return False, f"Login failed: status={response.status_code}"


def check_templates(errors):
    print("\n" + "=" * 60)
    print("1) TEMPLATE url_for ENDPOINTS")
    print("=" * 60)

    real_endpoints = set(app.view_functions.keys())
    for endpoint in sorted(collect_template_endpoints()):
        if endpoint not in real_endpoints:
            msg = f"Missing endpoint in templates: {endpoint}"
            log_err(msg)
            errors.append(msg)
        else:
            log_ok(endpoint)


def check_schema(errors):
    print("\n" + "=" * 60)
    print("2) DATABASE SCHEMA")
    print("=" * 60)

    conn = connect_db()
    cur = conn.cursor()

    for table in sorted(REQUIRED_TABLES):
        if table_exists(cur, table):
            log_ok(f"table exists: {table}")
        else:
            msg = f"Missing table: {table}"
            log_err(msg)
            errors.append(msg)

    for table, required in REQUIRED_COLUMNS.items():
        cols = columns(cur, table)
        if not cols:
            continue
        missing = sorted(required - cols)
        if missing:
            msg = f"Table {table} missing columns: {missing}"
            log_err(msg)
            errors.append(msg)
        else:
            log_ok(f"columns OK: {table}")

    conn.close()


def check_login(errors):
    print("\n" + "=" * 60)
    print("3) LOGIN")
    print("=" * 60)

    client = app.test_client()
    ok, msg = login(client)
    if ok:
        log_ok(msg)
        return client
    log_err(msg)
    errors.append(msg)
    return None


def request_check(client, url, errors, allowed_redirect=False):
    try:
        response = client.get(url, follow_redirects=False)

        if response.status_code >= 500:
            msg = f"{url} returned {response.status_code}"
            log_err(msg)
            errors.append(msg)
        elif response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location", "")
            if allowed_redirect:
                log_ok(f"{url} -> {response.status_code} allowed redirect to {location}")
            else:
                msg = f"{url} redirected -> {response.status_code} Location: {location}"
                log_err(msg)
                errors.append(msg)
        elif response.status_code >= 400:
            msg = f"{url} returned {response.status_code}"
            log_err(msg)
            errors.append(msg)
        else:
            log_ok(f"{url} -> {response.status_code}")
    except Exception as e:
        msg = f"Exception on {url}: {e}"
        log_err(msg)
        traceback.print_exc()
        errors.append(msg)


def check_static_routes(client, errors, warnings):
    print("\n" + "=" * 60)
    print("5) STATIC ROUTES")
    print("=" * 60)

    for rule in app.url_map.iter_rules():
        endpoint = rule.endpoint
        url = rule.rule

        if endpoint in SKIP_ENDPOINTS:
            continue
        if url in SKIP_URLS:
            log_warn(f"SKIP {url} -> clears session")
            warnings.append(f"Skipped session route: {url}")
            continue
        if "GET" not in rule.methods:
            continue
        if rule.arguments:
            continue

        request_check(client, url, errors, allowed_redirect=(url in ALLOWED_REDIRECTS))


def check_dynamic_urls(client, errors, warnings):
    print("\n" + "=" * 60)
    print("6) DYNAMIC ROUTES USING TEST DATA")
    print("=" * 60)

    if not SEED_OK:
        msg = "Dynamic route test skipped because seed data failed."
        log_warn(msg)
        warnings.append(msg)
        return

    dynamic_urls = []

    if CREATED.get("sale_id"):
        sid = CREATED["sale_id"]
        dynamic_urls += [f"/sales/{sid}/edit", f"/sales/{sid}/export", f"/sales/{sid}/print"]

    if CREATED.get("purchase_id"):
        pid = CREATED["purchase_id"]
        dynamic_urls += [f"/purchases/{pid}/edit", f"/purchases/{pid}/export", f"/purchases/{pid}/print"]

    if CREATED.get("customer_id"):
        cid = CREATED["customer_id"]
        dynamic_urls += [f"/customers/{cid}/edit", f"/customers/{cid}/statement"]

    if CREATED.get("supplier_id"):
        sid = CREATED["supplier_id"]
        dynamic_urls += [f"/suppliers/{sid}/edit", f"/suppliers/{sid}/statement"]

    if CREATED.get("product_id"):
        pid = CREATED["product_id"]
        dynamic_urls += [f"/products/{pid}/edit", f"/products/{pid}/barcode"]

    if CREATED.get("receipt_id"):
        rid = CREATED["receipt_id"]
        dynamic_urls += [f"/receipts/{rid}/edit", f"/receipts/{rid}/print"]

    if CREATED.get("payment_id"):
        payid = CREATED["payment_id"]
        dynamic_urls += [f"/payments/{payid}/edit", f"/payments/{payid}/print"]

    if not dynamic_urls:
        msg = "No dynamic URLs created."
        log_warn(msg)
        warnings.append(msg)
        return

    for url in dynamic_urls:
        request_check(client, url, errors)


def check_reports(client, errors):
    print("\n" + "=" * 60)
    print("7) KEY REPORTS")
    print("=" * 60)

    report_urls = [
        "/reports/inventory",
        "/reports/customers",
        "/reports/suppliers",
        "/reports/customers/aging",
        "/reports/suppliers/aging",
        "/reports/balance-sheet",
        "/reports/cash-flow",
        "/reports/cost-centers",
        "/reports/profit-loss",
        "/reports/vat",
        "/trial-balance",
        "/journal",
        "/ledger/1",
    ]

    for url in report_urls:
        request_check(client, url, errors)


def check_integrity(errors, warnings):
    print("\n" + "=" * 60)
    print("8) DATA INTEGRITY")
    print("=" * 60)

    checks = [
        ("Negative product stock", "SELECT COUNT(*) FROM products WHERE COALESCE(stock_quantity,0) < 0"),
        ("Sales lines missing invoice", "SELECT COUNT(*) FROM sales_invoice_lines l LEFT JOIN sales_invoices s ON s.id=l.invoice_id WHERE s.id IS NULL"),
        ("Purchase lines missing invoice", "SELECT COUNT(*) FROM purchase_invoice_lines l LEFT JOIN purchase_invoices p ON p.id=l.invoice_id WHERE p.id IS NULL"),
        ("Sales missing product", "SELECT COUNT(*) FROM sales_invoices s LEFT JOIN products p ON p.id=s.product_id WHERE s.product_id IS NOT NULL AND p.id IS NULL"),
        ("Purchases missing product", "SELECT COUNT(*) FROM purchase_invoices pi LEFT JOIN products p ON p.id=pi.product_id WHERE pi.product_id IS NOT NULL AND p.id IS NULL"),
    ]

    conn = connect_db()
    cur = conn.cursor()

    for label, sql in checks:
        try:
            cur.execute(sql)
            count = cur.fetchone()[0]
            if count:
                msg = f"{label}: {count}"
                log_warn(msg)
                warnings.append(msg)
            else:
                log_ok(f"{label}: 0")
        except sqlite3.Error as e:
            msg = f"{label} check failed: {e}"
            log_warn(msg)
            warnings.append(msg)

    conn.close()


def print_summary(errors, warnings):
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Errors: {len(errors)}")
    print(f"Warnings: {len(warnings)}")

    if errors:
        print("\nErrors:")
        for e in errors:
            print("-", e)

    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print("-", w)

    print("\n" + "=" * 60)
    print("FINAL RESULT")
    print("=" * 60)

    if errors:
        print("FAILED ❌")
        raise SystemExit(1)
    print("PASSED ✅")


def main():
    errors = []
    warnings = []

    print("=" * 60)
    print("ERP ULTIMATE WORKFLOW TEST V2")
    print("=" * 60)
    print("Run this on a COPY of the project/database only.")
    print(f"DB_PATH: {DB_PATH}")
    print(f"TEST USER: {TEST_USERNAME}")
    print(f"TEST TAG: {TEST_TAG}")

    check_templates(errors)
    check_schema(errors)

    try:
        seed_data()
    except Exception as e:
        msg = f"Could not seed test data: {e}"
        log_err(msg)
        traceback.print_exc()
        errors.append(msg)

    client = check_login(errors)

    if client:
        check_static_routes(client, errors, warnings)
        check_dynamic_urls(client, errors, warnings)
        check_reports(client, errors)
        check_integrity(errors, warnings)

    print_summary(errors, warnings)


if __name__ == "__main__":
    main()
