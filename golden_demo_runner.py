import base64
import json
import os
import shutil
import sqlite3
from datetime import datetime
from io import BytesIO

import app


BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "database.db")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
TAG = "GOLDEN DEMO E2E 2026-04-21"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z8MsAAAAASUVORK5CYII="
)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def scalar(query, params=()):
    conn = db()
    cur = conn.cursor()
    cur.execute(query, params)
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return row[0]


def row(query, params=()):
    conn = db()
    cur = conn.cursor()
    cur.execute(query, params)
    result = cur.fetchone()
    conn.close()
    return result


def rows(query, params=()):
    conn = db()
    cur = conn.cursor()
    cur.execute(query, params)
    result = cur.fetchall()
    conn.close()
    return result


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


class DemoRunner:
    def __init__(self):
        self.client = app.app.test_client()
        self.viewer_client = app.app.test_client()
        self.results = []
        self.failures = []
        self.created = {}
        self.backup_path = None
        self.original_logo = None
        self.original_logo_file = None

    def log(self, name, status, details=""):
        self.results.append({"step": name, "status": status, "details": details})

    def admin_session(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "admin"
            session["role"] = "admin"

    def viewer_session(self):
        with self.viewer_client.session_transaction() as session:
            session["user_id"] = 2
            session["username"] = "1001"
            session["role"] = "viewer"

    def backup_db(self):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        self.backup_path = os.path.join(BACKUP_DIR, f"golden-demo-before-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db")
        shutil.copy2(DB_PATH, self.backup_path)
        self.log("backup", "ok", self.backup_path)

    def inspect_environment(self):
        key_tables = [
            "users",
            "company_settings",
            "posting_control",
            "fiscal_periods",
            "accounts",
            "cost_centers",
            "customers",
            "suppliers",
            "products",
            "sales_orders",
            "sales_delivery_notes",
            "sales_invoices",
            "purchase_orders",
            "purchase_receipts",
            "purchase_invoices",
            "journal",
            "ledger",
        ]
        existing = []
        for table_name in key_tables:
            if scalar("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (table_name,)):
                existing.append(table_name)
        assert_true(len(existing) == len(key_tables), "Not all required tables exist for the golden demo.")
        self.log("schema", "ok", f"{len(existing)} tables ready")

    def smoke_get(self, path, client=None):
        response = (client or self.client).get(path, follow_redirects=True)
        assert_true(response.status_code == 200, f"GET {path} failed with status {response.status_code}")
        self.log(f"GET {path}", "ok")
        return response

    def post(self, path, data=None, content_type=None, client=None):
        response = (client or self.client).post(path, data=data or {}, content_type=content_type, follow_redirects=True)
        assert_true(response.status_code == 200, f"POST {path} failed with status {response.status_code}")
        self.log(f"POST {path}", "ok")
        return response

    def create_or_get_customer(self, name, withholding_status):
        customer = row("SELECT id FROM customers WHERE name=?", (name,))
        if customer:
            return customer["id"]
        self.post(
            "/customers",
            {
                "name": name,
                "phone": "01000000000",
                "address": f"{TAG} Address",
                "tax_registration_number": "123456789",
                "tax_card_number": "987654321",
                "contact_person": TAG,
                "email": f"{name.replace(' ', '').lower()}@demo.local",
                "withholding_status": withholding_status,
            },
        )
        customer_id = scalar("SELECT id FROM customers WHERE name=?", (name,))
        assert_true(customer_id is not None, f"Customer {name} was not created")
        return customer_id

    def create_or_get_supplier(self, name, withholding_status):
        supplier = row("SELECT id FROM suppliers WHERE name=?", (name,))
        if supplier:
            return supplier["id"]
        self.post(
            "/suppliers",
            {
                "name": name,
                "phone": "01000000001",
                "address": f"{TAG} Supplier Address",
                "tax_registration_number": "123123123",
                "tax_card_number": "321321321",
                "contact_person": TAG,
                "email": f"{name.replace(' ', '').lower()}@demo.local",
                "withholding_status": withholding_status,
            },
        )
        supplier_id = scalar("SELECT id FROM suppliers WHERE name=?", (name,))
        assert_true(supplier_id is not None, f"Supplier {name} was not created")
        return supplier_id

    def create_or_get_product(self, code, name, supplier_id):
        product = row("SELECT id FROM products WHERE code=?", (code,))
        if product:
            return product["id"]
        self.post(
            "/products",
            {
                "code": code,
                "name": name,
                "unit": "قطعة",
                "purchase_price": "50",
                "sale_price": "80",
                "default_supplier_id": str(supplier_id),
            },
        )
        product_id = scalar("SELECT id FROM products WHERE code=?", (code,))
        assert_true(product_id is not None, f"Product {code} was not created")
        return product_id

    def run(self):
        self.admin_session()
        self.viewer_session()
        self.backup_db()
        self.inspect_environment()

        self.original_logo = scalar("SELECT logo_path FROM company_settings WHERE id=1")
        if self.original_logo and self.original_logo.startswith("/static/"):
            logo_fs_path = os.path.join(BASE_DIR, self.original_logo.lstrip("/").replace("/", os.sep))
            if os.path.exists(logo_fs_path):
                with open(logo_fs_path, "rb") as file_obj:
                    self.original_logo_file = file_obj.read()

        self.run_core_master_checks()
        self.run_sales_cycle()
        self.run_purchase_cycle()
        self.run_journal_checks()
        self.run_reports_checks()
        self.run_accounting_verification()

        return {
            "backup_path": self.backup_path,
            "results": self.results,
            "created": self.created,
        }

    def run_core_master_checks(self):
        for path in [
            "/dashboard",
            "/settings/company",
            "/posting-control",
            "/fiscal-periods",
            "/accounts",
            "/cost-centers",
            "/users",
            "/permissions",
            "/customers",
            "/suppliers",
            "/products",
            "/inventory",
        ]:
            self.smoke_get(path)

        self.post(
            "/settings/company",
            data={
                "company_name": scalar("SELECT company_name FROM company_settings WHERE id=1") or "ERP Demo",
                "tax_number": scalar("SELECT tax_number FROM company_settings WHERE id=1") or "",
                "commercial_register": scalar("SELECT commercial_register FROM company_settings WHERE id=1") or "",
                "address": scalar("SELECT address FROM company_settings WHERE id=1") or "",
                "phone": scalar("SELECT phone FROM company_settings WHERE id=1") or "",
                "email": scalar("SELECT email FROM company_settings WHERE id=1") or "",
                "default_tax_rate": str(scalar("SELECT default_tax_rate FROM company_settings WHERE id=1") or 14),
                "invoice_footer": scalar("SELECT invoice_footer FROM company_settings WHERE id=1") or "",
                "company_logo": (BytesIO(PNG_1X1), "golden-demo-logo.png"),
            },
            content_type="multipart/form-data",
        )
        assert_true((scalar("SELECT logo_path FROM company_settings WHERE id=1") or "").endswith(".png"), "Company logo upload did not persist a PNG path.")
        if self.original_logo and self.original_logo.startswith("/static/") and self.original_logo_file is not None:
            logo_fs_path = os.path.join(BASE_DIR, self.original_logo.lstrip("/").replace("/", os.sep))
            with open(logo_fs_path, "wb") as file_obj:
                file_obj.write(self.original_logo_file)

        future_period_name = f"{TAG} PERIOD"
        if not scalar("SELECT id FROM fiscal_periods WHERE name=?", (future_period_name,)):
            self.post(
                "/fiscal-periods",
                {
                    "name": future_period_name,
                    "start_date": "2030-01-01",
                    "end_date": "2030-12-31",
                    "notes": TAG,
                },
            )
        period_id = scalar("SELECT id FROM fiscal_periods WHERE name=?", (future_period_name,))
        self.post(f"/fiscal-periods/{period_id}/close", {})
        status_after_close = scalar("SELECT status FROM fiscal_periods WHERE id=?", (period_id,))
        assert_true(status_after_close == "closed", "Fiscal period did not close.")
        self.post(f"/fiscal-periods/{period_id}/open", {}, client=self.viewer_client)
        assert_true(scalar("SELECT status FROM fiscal_periods WHERE id=?", (period_id,)) == "closed", "Viewer should not be able to reopen a closed period.")
        self.post(f"/fiscal-periods/{period_id}/open", {})
        assert_true(scalar("SELECT status FROM fiscal_periods WHERE id=?", (period_id,)) == "open", "Admin reopen of fiscal period failed.")
        self.created["fiscal_period_id"] = period_id

        account_code = "99991"
        if not scalar("SELECT id FROM accounts WHERE code=?", (account_code,)):
            self.post("/accounts", {"code": account_code, "name": f"{TAG} TEST ACCOUNT", "type": "مصروفات"})
        account_id = scalar("SELECT id FROM accounts WHERE code=?", (account_code,))
        self.post(f"/accounts/edit/{account_id}", {"code": "99992", "name": f"{TAG} TEST ACCOUNT EDITED", "type": "مصروفات"})
        edited_account_id = scalar("SELECT id FROM accounts WHERE code='99992'")
        assert_true(edited_account_id == account_id, "Account edit did not persist.")
        self.post(f"/accounts/delete/{account_id}", {})
        assert_true(scalar("SELECT COUNT(*) FROM accounts WHERE id=?", (account_id,)) == 0, "Account delete failed for unused test account.")

        if not scalar("SELECT id FROM cost_centers WHERE code='GD-CC-E2E'"):
            self.post("/cost-centers", {"code": "GD-CC-E2E", "name": f"{TAG} COST CENTER", "center_type": "تشغيلي", "notes": TAG})
        cost_center_id = scalar("SELECT id FROM cost_centers WHERE code='GD-CC-E2E'")
        self.created["cost_center_id"] = cost_center_id

        viewer_username = "golden_demo_viewer"
        if not scalar("SELECT id FROM users WHERE username=?", (viewer_username,)):
            self.post("/users", {"username": viewer_username, "password": "demo123", "role": "viewer"})
        self.created["viewer_user_id"] = scalar("SELECT id FROM users WHERE username=?", (viewer_username,))

        perm_rows = rows("SELECT role,permission_key,access_level FROM role_permissions")
        perm_data = {}
        for role_name in ["accountant", "sales", "viewer"]:
            for permission_key in [r["permission_key"] for r in rows("SELECT DISTINCT permission_key FROM role_permissions ORDER BY permission_key")]:
                level = next((r["access_level"] for r in perm_rows if r["role"] == role_name and r["permission_key"] == permission_key), "none")
                perm_data[f"{role_name}__{permission_key}"] = level
        self.post("/permissions", perm_data)

        subject_customer = self.create_or_get_customer(f"{TAG} CUSTOMER SUBJECT", "subject")
        normal_customer = self.create_or_get_customer(f"{TAG} CUSTOMER NORMAL", "non_subject")
        taxable_supplier = self.create_or_get_supplier(f"{TAG} SUPPLIER TAXABLE", "taxable")
        exempt_supplier = self.create_or_get_supplier(f"{TAG} SUPPLIER EXEMPT", "exempt")
        demo_product = self.create_or_get_product("GD-E2E-ITEM-A", f"{TAG} ITEM A", taxable_supplier)
        temp_product = self.create_or_get_product("GD-E2E-TEMP", f"{TAG} TEMP ITEM", taxable_supplier)

        self.created.update(
            {
                "customer_subject_id": subject_customer,
                "customer_normal_id": normal_customer,
                "supplier_taxable_id": taxable_supplier,
                "supplier_exempt_id": exempt_supplier,
                "product_demo_id": demo_product,
                "product_temp_id": temp_product,
            }
        )

        self.post(
            f"/customers/{subject_customer}/edit",
            {
                "name": f"{TAG} CUSTOMER SUBJECT",
                "phone": "01111111111",
                "address": f"{TAG} Customer Address Updated",
                "tax_registration_number": "123456789",
                "tax_card_number": "987654321",
                "contact_person": "Golden Contact",
                "email": "golden.customer.subject@demo.local",
                "withholding_status": "subject",
            },
        )
        self.post(
            f"/suppliers/{taxable_supplier}/edit",
            {
                "name": f"{TAG} SUPPLIER TAXABLE",
                "phone": "01222222222",
                "address": f"{TAG} Supplier Address Updated",
                "tax_registration_number": "222333444",
                "tax_card_number": "444333222",
                "contact_person": "Golden Supplier Contact",
                "email": "golden.supplier.taxable@demo.local",
                "withholding_status": "taxable",
            },
        )
        self.post(
            f"/products/{demo_product}/edit",
            {
                "code": "GD-E2E-ITEM-A",
                "name": f"{TAG} ITEM A",
                "unit": "قطعة",
                "purchase_price": "50",
                "sale_price": "80",
                "default_supplier_id": str(taxable_supplier),
            },
        )

        temp_customer = self.create_or_get_customer(f"{TAG} CUSTOMER TEMP DELETE", "non_subject")
        temp_supplier = self.create_or_get_supplier(f"{TAG} SUPPLIER TEMP DELETE", "exempt")
        self.post(f"/customers/{temp_customer}/delete", {})
        self.post(f"/suppliers/{temp_supplier}/delete", {})
        self.post(f"/products/{temp_product}/delete", {})
        assert_true(scalar("SELECT COUNT(*) FROM customers WHERE id=?", (temp_customer,)) == 0, "Temporary customer delete failed.")
        assert_true(scalar("SELECT COUNT(*) FROM suppliers WHERE id=?", (temp_supplier,)) == 0, "Temporary supplier delete failed.")
        assert_true(scalar("SELECT COUNT(*) FROM products WHERE id=?", (temp_product,)) == 0, "Temporary product delete failed.")

    def run_sales_cycle(self):
        demo_product = self.created["product_demo_id"]
        customer_subject = self.created["customer_subject_id"]
        customer_normal = self.created["customer_normal_id"]

        # Seed stock via taxable purchase cycle first if needed.
        if (scalar("SELECT stock_quantity FROM products WHERE id=?", (demo_product,)) or 0) < 20:
            current_stock = scalar("SELECT stock_quantity FROM products WHERE id=?", (demo_product,)) or 0
            conn = db()
            cur = conn.cursor()
            cur.execute("UPDATE products SET stock_quantity=? WHERE id=?", (20, demo_product))
            conn.commit()
            conn.close()
            self.log("stock seed", "ok", f"raised demo product stock from {current_stock} to 20 for clean sales demo")

        self.post(
            "/sales-orders",
            {
                "date": "2026-04-21",
                "customer_id": str(customer_subject),
                "payment_terms": "30 يوم",
                "delivery_date": "2026-04-21",
                "notes": TAG,
                "product_id[]": [str(demo_product)],
                "quantity[]": ["4"],
                "unit_price[]": ["80"],
                "tax_rate[]": ["14"],
            },
        )
        sales_order_id = scalar("SELECT id FROM sales_orders WHERE notes=? ORDER BY id DESC LIMIT 1", (TAG,))
        line_id = scalar("SELECT id FROM sales_order_lines WHERE order_id=? ORDER BY id DESC LIMIT 1", (sales_order_id,))
        self.created["sales_order_id"] = sales_order_id

        self.post(
            "/sales-deliveries",
            {
                "date": "2026-04-21",
                "sales_order_line_id": str(line_id),
                "delivered_quantity": "4",
                "notes": TAG,
            },
        )
        delivery_id = scalar("SELECT id FROM sales_delivery_notes WHERE sales_order_line_id=? ORDER BY id DESC LIMIT 1", (line_id,))
        self.created["sales_delivery_id"] = delivery_id

        self.post(
            "/sales/from-delivery",
            {
                "delivery_ids": [str(delivery_id)],
                "date": "2026-04-21",
                "due_date": "2026-05-21",
                "payment_type": "credit",
                "po_ref": "PO-GD-SUBJECT",
                "gr_ref": "GR-GD-SUBJECT",
                "notes": TAG,
            },
        )
        delivery_invoice_id = scalar("SELECT id FROM sales_invoices WHERE sales_delivery_id=? ORDER BY id DESC LIMIT 1", (delivery_id,))
        self.created["sales_invoice_subject_id"] = delivery_invoice_id
        withholding_amount = scalar("SELECT withholding_amount FROM sales_invoices WHERE id=?", (delivery_invoice_id,))
        assert_true((withholding_amount or 0) > 0, "Subject customer sales invoice did not calculate withholding.")
        assert_true(scalar("SELECT invoice_id FROM sales_delivery_notes WHERE id=?", (delivery_id,)) == delivery_invoice_id, "Sales delivery did not link to created invoice.")

        self.post(
            "/sales",
            {
                "date": "2026-04-21",
                "due_date": "2026-05-21",
                "customer_id": str(customer_normal),
                "product_id": str(demo_product),
                "payment_type": "credit",
                "tax_rate": "14",
                "quantity": "2",
                "unit_price": "90",
                "po_ref": "PO-GD-NORMAL",
                "gr_ref": "GR-GD-NORMAL",
                "notes": f"{TAG} NORMAL SALE",
            },
        )
        direct_invoice_id = scalar("SELECT id FROM sales_invoices WHERE notes=? ORDER BY id DESC LIMIT 1", (f"{TAG} NORMAL SALE",))
        self.created["sales_invoice_normal_id"] = direct_invoice_id
        assert_true((scalar("SELECT withholding_amount FROM sales_invoices WHERE id=?", (direct_invoice_id,)) or 0) == 0, "Non-subject customer invoice should not calculate withholding.")

        self.post(
            "/receipts",
            {
                "date": "2026-04-21",
                "customer_id": str(customer_subject),
                "amount": "100",
                "notes": TAG,
            },
        )
        receipt_id = scalar("SELECT id FROM receipt_vouchers WHERE notes=? ORDER BY id DESC LIMIT 1", (TAG,))
        self.created["receipt_id"] = receipt_id

        self.post(
            "/returns/sales",
            {
                "date": "2026-04-21",
                "sales_invoice_id": str(delivery_invoice_id),
                "product_id[]": [str(demo_product)],
                "quantity[]": ["1"],
                "po_ref": "PO-RET-SALE",
                "gr_ref": "GR-RET-SALE",
                "notes": TAG,
            },
        )
        sales_return_id = scalar("SELECT id FROM sales_returns WHERE notes=? ORDER BY id DESC LIMIT 1", (TAG,))
        self.created["sales_return_id"] = sales_return_id

        self.post(
            "/credit-notes/sales",
            {
                "date": "2026-04-21",
                "sales_return_id": str(sales_return_id),
                "notes": TAG,
            },
        )
        credit_note_id = scalar("SELECT id FROM sales_credit_notes WHERE sales_return_id=?", (sales_return_id,))
        self.created["sales_credit_note_id"] = credit_note_id

        # Downstream checks
        assert_true(scalar("SELECT COUNT(*) FROM inventory_movements WHERE reference_type='sales_delivery' AND reference_id=?", (delivery_id,)) == 1, "Sales delivery inventory movement missing.")
        assert_true(scalar("SELECT COUNT(*) FROM inventory_movements WHERE reference_type='sale' AND reference_id=?", (direct_invoice_id,)) == 1, "Direct sales invoice inventory movement missing.")
        assert_true(scalar("SELECT COUNT(*) FROM inventory_movements WHERE reference_type='sales_return' AND reference_id=?", (sales_return_id,)) == 1, "Sales return inventory movement missing.")

        subject_statement = self.smoke_get(f"/customers/{customer_subject}/statement")
        assert_true(subject_statement.status_code == 200, "Customer statement failed.")

    def run_purchase_cycle(self):
        demo_product = self.created["product_demo_id"]
        taxable_supplier = self.created["supplier_taxable_id"]
        exempt_supplier = self.created["supplier_exempt_id"]

        self.post(
            "/purchase-orders",
            {
                "date": "2026-04-21",
                "supplier_id": str(taxable_supplier),
                "payment_terms": "45 يوم",
                "delivery_date": "2026-04-21",
                "delivery_terms": "توريد مخزني",
                "notes": TAG,
                "product_id[]": [str(demo_product)],
                "quantity[]": ["10"],
                "unit_price[]": ["50"],
                "tax_rate[]": ["14"],
            },
        )
        purchase_order_id = scalar("SELECT id FROM purchase_orders WHERE notes=? ORDER BY id DESC LIMIT 1", (TAG,))
        po_line_id = scalar("SELECT id FROM purchase_order_lines WHERE order_id=? ORDER BY id DESC LIMIT 1", (purchase_order_id,))
        self.created["purchase_order_id"] = purchase_order_id

        self.post(
            "/purchase-receipts",
            {
                "date": "2026-04-21",
                "purchase_order_line_id": str(po_line_id),
                "received_quantity": "10",
                "notes": TAG,
            },
        )
        receipt_id = scalar("SELECT id FROM purchase_receipts WHERE purchase_order_line_id=? ORDER BY id DESC LIMIT 1", (po_line_id,))
        self.created["purchase_receipt_id"] = receipt_id

        self.post(
            "/purchases/from-receipt",
            {
                "receipt_ids": [str(receipt_id)],
                "date": "2026-04-21",
                "supplier_invoice_no": "GD-TAX-001",
                "supplier_invoice_date": "2026-04-21",
                "due_date": "2026-05-21",
                "payment_type": "credit",
                "notes": TAG,
            },
        )
        receipt_invoice_id = scalar("SELECT id FROM purchase_invoices WHERE purchase_receipt_id=? ORDER BY id DESC LIMIT 1", (receipt_id,))
        self.created["purchase_invoice_taxable_id"] = receipt_invoice_id
        assert_true((scalar("SELECT withholding_amount FROM purchase_invoices WHERE id=?", (receipt_invoice_id,)) or 0) > 0, "Taxable supplier invoice from receipt did not calculate withholding.")
        assert_true(scalar("SELECT invoice_id FROM purchase_receipts WHERE id=?", (receipt_id,)) == receipt_invoice_id, "Purchase receipt did not link to supplier invoice.")

        self.post(
            "/purchases",
            {
                "date": "2026-04-21",
                "supplier_invoice_no": "GD-EX-001",
                "supplier_invoice_date": "2026-04-21",
                "due_date": "2026-05-21",
                "supplier_id": str(exempt_supplier),
                "product_id": str(demo_product),
                "payment_type": "credit",
                "tax_rate": "14",
                "quantity": "5",
                "unit_price": "52",
                "notes": f"{TAG} EXEMPT PURCHASE",
            },
        )
        direct_purchase_invoice_id = scalar("SELECT id FROM purchase_invoices WHERE notes=? ORDER BY id DESC LIMIT 1", (f"{TAG} EXEMPT PURCHASE",))
        self.created["purchase_invoice_exempt_id"] = direct_purchase_invoice_id
        assert_true((scalar("SELECT withholding_amount FROM purchase_invoices WHERE id=?", (direct_purchase_invoice_id,)) or 0) == 0, "Exempt supplier invoice should not calculate withholding.")

        self.post(
            "/payments",
            {
                "date": "2026-04-21",
                "supplier_id": str(taxable_supplier),
                "amount": "100",
                "notes": TAG,
            },
        )
        payment_id = scalar("SELECT id FROM payment_vouchers WHERE notes=? ORDER BY id DESC LIMIT 1", (TAG,))
        self.created["payment_id"] = payment_id

        self.post(
            "/returns/purchases",
            {
                "date": "2026-04-21",
                "purchase_invoice_id": str(direct_purchase_invoice_id),
                "product_id[]": [str(demo_product)],
                "quantity[]": ["1"],
                "po_ref": "PO-RET-PUR",
                "gr_ref": "GR-RET-PUR",
                "notes": TAG,
            },
        )
        purchase_return_id = scalar("SELECT id FROM purchase_returns WHERE notes=? ORDER BY id DESC LIMIT 1", (TAG,))
        self.created["purchase_return_id"] = purchase_return_id

        assert_true(scalar("SELECT COUNT(*) FROM inventory_movements WHERE reference_type='purchase_receipt' AND reference_id=?", (receipt_id,)) == 1, "Purchase receipt inventory movement missing.")
        assert_true(scalar("SELECT COUNT(*) FROM inventory_movements WHERE reference_type='purchase' AND reference_id=?", (direct_purchase_invoice_id,)) == 1, "Direct purchase invoice inventory movement missing.")
        assert_true(scalar("SELECT COUNT(*) FROM inventory_movements WHERE reference_type='purchase_return' AND reference_id=?", (purchase_return_id,)) == 1, "Purchase return inventory movement missing.")

        supplier_statement = self.smoke_get(f"/suppliers/{taxable_supplier}/statement")
        assert_true(supplier_statement.status_code == 200, "Supplier statement failed.")

    def run_journal_checks(self):
        # Unpost manual group so create/edit/delete can be tested on drafts.
        self.post("/posting-control/manual_journal/unpost", {})
        assert_true(scalar("SELECT is_posted FROM posting_control WHERE group_key='manual_journal'") == 0, "Manual journal group did not unpost.")

        debit_account_id = scalar("SELECT id FROM accounts WHERE code='1100'")
        credit_account_id = scalar("SELECT id FROM accounts WHERE code='2100'")
        cost_center_id = self.created["cost_center_id"]

        self.post(
            "/journal",
            {
                "date": "2026-04-21",
                "description": f"{TAG} JOURNAL KEEP",
                "debit": str(debit_account_id),
                "credit": str(credit_account_id),
                "amount": "75",
                "cost_center_id": str(cost_center_id),
            },
        )
        keep_id = scalar("SELECT id FROM journal WHERE description=? ORDER BY id DESC LIMIT 1", (f"{TAG} JOURNAL KEEP",))
        self.created["journal_keep_id"] = keep_id

        self.post(
            "/journal",
            {
                "date": "2026-04-21",
                "description": f"{TAG} JOURNAL DELETE",
                "debit": str(credit_account_id),
                "credit": str(debit_account_id),
                "amount": "33",
                "cost_center_id": "",
            },
        )
        delete_id = scalar("SELECT id FROM journal WHERE description=? ORDER BY id DESC LIMIT 1", (f"{TAG} JOURNAL DELETE",))

        self.post(
            f"/edit/{keep_id}",
            {
                "date": "2026-04-21",
                "description": f"{TAG} JOURNAL KEEP EDITED",
                "debit": str(debit_account_id),
                "credit": str(credit_account_id),
                "amount": "80",
                "cost_center_id": str(cost_center_id),
            },
        )
        assert_true(scalar("SELECT description FROM journal WHERE id=?", (keep_id,)) == f"{TAG} JOURNAL KEEP EDITED", "Journal edit failed while group was unposted.")

        self.post(f"/delete/{delete_id}", {})
        assert_true(scalar("SELECT COUNT(*) FROM journal WHERE id=?", (delete_id,)) == 0, "Draft manual journal delete failed.")

        self.post("/posting-control/manual_journal/post", {})
        assert_true(scalar("SELECT is_posted FROM posting_control WHERE group_key='manual_journal'") == 1, "Manual journal group did not repost.")
        assert_true(scalar("SELECT status FROM journal WHERE id=?", (keep_id,)) == "posted", "Manual journal was not reposted.")
        assert_true(scalar("SELECT COUNT(*) FROM ledger WHERE journal_id=?", (keep_id,)) == 2, "Reposted manual journal did not rebuild ledger rows.")

        # Test delete prevention on referenced entities.
        self.post(f"/customers/{self.created['customer_subject_id']}/delete", {})
        assert_true(scalar("SELECT COUNT(*) FROM customers WHERE id=?", (self.created["customer_subject_id"],)) == 1, "Referenced customer should not be deletable.")
        self.post(f"/suppliers/{self.created['supplier_taxable_id']}/delete", {})
        assert_true(scalar("SELECT COUNT(*) FROM suppliers WHERE id=?", (self.created["supplier_taxable_id"],)) == 1, "Referenced supplier should not be deletable.")
        self.post(f"/products/{self.created['product_demo_id']}/delete", {})
        assert_true(scalar("SELECT COUNT(*) FROM products WHERE id=?", (self.created["product_demo_id"],)) == 1, "Referenced product should not be deletable.")

        self.smoke_get("/posting-control")
        self.smoke_get("/journal")

    def run_reports_checks(self):
        cash_account_id = scalar("SELECT id FROM accounts WHERE code='1100'")
        for path in [
            "/reports/inventory",
            "/reports/customers",
            "/reports/suppliers",
            "/reports/customers/aging",
            "/reports/suppliers/aging",
            "/trial-balance",
            f"/ledger/{cash_account_id}",
            "/audit-log",
            "/reports/balance-sheet",
            "/reports/cash-flow",
            "/reports/profit-loss",
            "/reports/vat",
            "/e-invoices",
        ]:
            self.smoke_get(path)

        for path in [
            "/journal/export",
            "/trial-balance/export",
            "/reports/inventory?format=excel",
            "/reports/customers?format=excel",
            "/reports/suppliers?format=excel",
            "/reports/customers/aging?format=excel",
            "/reports/suppliers/aging?format=excel",
        ]:
            response = self.smoke_get(path)
            assert_true(len(response.data) > 100, f"Export {path} returned an unexpectedly small payload.")

    def run_accounting_verification(self):
        total_debit = scalar("SELECT COALESCE(SUM(debit),0) FROM ledger") or 0
        total_credit = scalar("SELECT COALESCE(SUM(credit),0) FROM ledger") or 0
        assert_true(round(total_debit, 2) == round(total_credit, 2), f"Trial balance is not balanced: debit={total_debit}, credit={total_credit}")

        customer_subject = self.created["customer_subject_id"]
        supplier_taxable = self.created["supplier_taxable_id"]
        keep_id = self.created["journal_keep_id"]
        sales_invoice_subject_id = self.created["sales_invoice_subject_id"]
        sales_invoice_normal_id = self.created["sales_invoice_normal_id"]
        purchase_invoice_taxable_id = self.created["purchase_invoice_taxable_id"]
        purchase_invoice_exempt_id = self.created["purchase_invoice_exempt_id"]

        assert_true(scalar("SELECT COUNT(*) FROM journal WHERE source_type='sales' AND source_id=?", (sales_invoice_subject_id,)) >= 2, "Posted subject sales invoice did not generate expected journals.")
        assert_true(scalar("SELECT COUNT(*) FROM journal WHERE source_type='sales' AND source_id=?", (sales_invoice_normal_id,)) >= 1, "Posted normal sales invoice did not generate expected journals.")
        assert_true(scalar("SELECT COUNT(*) FROM journal WHERE source_type='purchases' AND source_id=?", (purchase_invoice_taxable_id,)) >= 2, "Posted taxable purchase invoice did not generate expected journals.")
        assert_true(scalar("SELECT COUNT(*) FROM journal WHERE source_type='purchases' AND source_id=?", (purchase_invoice_exempt_id,)) >= 1, "Posted exempt purchase invoice did not generate expected journals.")
        assert_true(scalar("SELECT COUNT(*) FROM ledger WHERE journal_id=?", (keep_id,)) == 2, "Manual journal does not appear in ledger.")

        customer_balance = row(
            """
            SELECT
                COALESCE(SUM(CASE WHEN payment_type='credit' AND status='posted' THEN grand_total - COALESCE(withholding_amount,0) ELSE 0 END),0)
            FROM sales_invoices
            WHERE customer_id=?
            """,
            (customer_subject,),
        )["COALESCE(SUM(CASE WHEN payment_type='credit' AND status='posted' THEN grand_total - COALESCE(withholding_amount,0) ELSE 0 END),0)"]
        customer_receipts = scalar("SELECT COALESCE(SUM(amount),0) FROM receipt_vouchers WHERE customer_id=? AND status='posted'", (customer_subject,)) or 0
        assert_true(customer_balance >= customer_receipts, "Customer receipts exceed posted customer invoices unexpectedly.")

        supplier_balance = scalar(
            "SELECT COALESCE(SUM(grand_total - COALESCE(withholding_amount,0)),0) FROM purchase_invoices WHERE supplier_id=? AND payment_type='credit' AND status='posted'",
            (supplier_taxable,),
        ) or 0
        supplier_payments = scalar("SELECT COALESCE(SUM(amount),0) FROM payment_vouchers WHERE supplier_id=? AND status='posted'", (supplier_taxable,)) or 0
        assert_true(supplier_balance >= supplier_payments, "Supplier payments exceed posted supplier invoices unexpectedly.")

        self.log("accounting verification", "ok", json.dumps({"debit": total_debit, "credit": total_credit}, ensure_ascii=False))


if __name__ == "__main__":
    runner = DemoRunner()
    result = runner.run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
