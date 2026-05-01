"""
LedgerX Clean Test Database Builder
-----------------------------------
يشغل على نسخة محلية فقط.

ماذا يفعل؟
1) يأخذ نسخة احتياطية من database.db
2) يشغل init_db من مشروعك لضمان توافق الجداول مع نفس نسخة البرنامج
3) يحذف العمليات التجريبية والحركات
4) ينشئ شجرة حسابات قياسية بسيطة مع أكواد ثابتة للاختبار
5) يضيف عميل ومورد وصنف واحد للتجربة

الاستخدام:
    python create_clean_ledger_test_db.py
"""

import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"

# تأكيد أن db.py سيستخدم نفس المسار المحلي
os.environ["ERP_DB_PATH"] = str(DB_PATH)

try:
    from db import init_db
except Exception as exc:
    raise SystemExit(f"Cannot import init_db from db.py. Run this file inside the ERP-SYSTEM folder. Error: {exc}")


TRANSACTION_TABLES = [
    "invoice_allocations",
    "sales_credit_notes",
    "supplier_debit_notes",
    "sales_returns",
    "purchase_returns",
    "sales_invoice_lines",
    "purchase_invoice_lines",
    "financial_sales_invoice_lines",
    "financial_sales_invoices",
    "sales_invoices",
    "purchase_invoices",
    "receipt_vouchers",
    "payment_vouchers",
    "customer_adjustments",
    "sales_delivery_notes",
    "purchase_receipts",
    "sales_order_lines",
    "purchase_order_lines",
    "sales_orders",
    "purchase_orders",
    "inventory_movements",
    "journal",
    "ledger",
    "year_end_closings",
    "safe_ultimate_test_log",
]

MASTER_OPTIONAL_TABLES = [
    "products",
    "product_categories",
    "customers",
    "suppliers",
    "cost_centers",
]

STANDARD_ACCOUNTS = [
    ("1000", "الأصول", "أصول"),
    ("1100", "الصندوق الرئيسي", "أصول"),
    ("1200", "البنك الرئيسي", "أصول"),
    ("1300", "العملاء", "أصول"),
    ("1400", "المخزون", "أصول"),
    ("1500", "ضريبة قيمة مضافة - مدخلات", "أصول"),
    ("1510", "ضريبة خصم وإضافة مدينة", "أصول"),
    ("2000", "الخصوم", "خصوم"),
    ("2100", "الموردون", "خصوم"),
    ("2200", "ضريبة قيمة مضافة - مخرجات", "خصوم"),
    ("2230", "ضريبة خصم وإضافة دائنة", "خصوم"),
    ("3000", "حقوق الملكية", "حقوق ملكية"),
    ("3100", "رأس المال", "حقوق ملكية"),
    ("4000", "الإيرادات", "إيرادات"),
    ("4100", "إيرادات المبيعات", "إيرادات"),
    ("4200", "مردودات ومسموحات المبيعات", "إيرادات"),
    ("4210", "مردودات ومسموحات المشتريات", "إيرادات"),
    ("5000", "المصروفات", "مصروفات"),
    ("5100", "مصروفات عمومية", "مصروفات"),
    ("6100", "تكلفة البضاعة المباعة", "مصروفات"),
]


def table_exists(cur, table):
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def column_names(cur, table):
    cur.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


def safe_delete(cur, table):
    if table_exists(cur, table):
        cur.execute(f"DELETE FROM {table}")


def reset_autoincrement(cur, table):
    if table_exists(cur, "sqlite_sequence"):
        cur.execute("DELETE FROM sqlite_sequence WHERE name=?", (table,))


def insert_if_columns(cur, table, data):
    cols = column_names(cur, table)
    payload = {k: v for k, v in data.items() if k in cols}
    if not payload:
        return
    keys = list(payload.keys())
    placeholders = ",".join("?" for _ in keys)
    cur.execute(
        f"INSERT INTO {table}({','.join(keys)}) VALUES ({placeholders})",
        [payload[k] for k in keys],
    )


def main():
    print("LedgerX clean test DB setup started...")

    # 1) Backup
    if DB_PATH.exists():
        backup_dir = BASE_DIR / "backups" / "local_clean_setup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"database_before_clean_{stamp}.db"
        shutil.copy2(DB_PATH, backup_path)
        print(f"Backup created: {backup_path}")

    # 2) Ensure schema
    init_db()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        cur.execute("PRAGMA foreign_keys = OFF")

        # 3) Delete transactions
        for table in TRANSACTION_TABLES:
            safe_delete(cur, table)
            reset_autoincrement(cur, table)

        # 4) Reset selected master data for clean testing
        for table in MASTER_OPTIONAL_TABLES:
            safe_delete(cur, table)
            reset_autoincrement(cur, table)

        # 5) Reset accounts to known testing codes
        safe_delete(cur, "accounts")
        reset_autoincrement(cur, "accounts")
        for code, name, acc_type in STANDARD_ACCOUNTS:
            cur.execute(
                "INSERT INTO accounts(code, name, type) VALUES (?, ?, ?)",
                (code, name, acc_type),
            )

        # 6) Company settings
        if table_exists(cur, "company_settings"):
            cur.execute("DELETE FROM company_settings")
            insert_if_columns(
                cur,
                "company_settings",
                {
                    "id": 1,
                    "company_name": "LedgerX Test Company",
                    "tax_number": "000000000",
                    "commercial_register": "TEST-CR",
                    "address": "القاهرة",
                    "phone": "01140320867",
                    "email": "test@example.com",
                    "default_tax_rate": 14,
                    "invoice_footer": "بيانات اختبار محلية",
                },
            )

        # 7) Seed customer, supplier, product
        if table_exists(cur, "customers"):
            insert_if_columns(
                cur,
                "customers",
                {
                    "id": 1,
                    "name": "عميل اختبار",
                    "phone": "01000000000",
                    "address": "القاهرة",
                    "tax_registration_number": "CUST-TAX-001",
                    "tax_card_number": "CUST-CARD-001",
                    "contact_person": "مسؤول العميل",
                    "email": "customer@example.com",
                    "withholding_status": "non_subject",
                },
            )

        if table_exists(cur, "suppliers"):
            insert_if_columns(
                cur,
                "suppliers",
                {
                    "id": 1,
                    "name": "مورد اختبار",
                    "phone": "01111111111",
                    "address": "القاهرة",
                    "tax_registration_number": "SUP-TAX-001",
                    "tax_card_number": "SUP-CARD-001",
                    "contact_person": "مسؤول المورد",
                    "email": "supplier@example.com",
                    "withholding_status": "exempt",
                },
            )

        if table_exists(cur, "products"):
            insert_if_columns(
                cur,
                "products",
                {
                    "id": 1,
                    "code": "P-001",
                    "name": "صنف اختبار",
                    "unit": "وحدة",
                    "purchase_price": 600,
                    "sale_price": 1000,
                    "stock_quantity": 100,
                    "default_supplier_id": 1,
                },
            )

        if table_exists(cur, "document_sequences"):
            # لا نمسح كل السيكوينس لو البرنامج معتمد عليها؛ نعيد ضبط الأنواع الشائعة فقط
            sequences = [
                ("sales", "S-", 1),
                ("purchases", "P-", 1),
                ("sales_credit_notes", "SCN-", 1),
                ("supplier_debit_notes", "SDN-", 1),
                ("customer_adjustments", "CADJ-", 1),
            ]
            for doc_type, prefix, next_number in sequences:
                cur.execute(
                    """
                    INSERT INTO document_sequences(doc_type, prefix, next_number)
                    VALUES (?, ?, ?)
                    ON CONFLICT(doc_type) DO UPDATE SET prefix=excluded.prefix, next_number=excluded.next_number
                    """,
                    (doc_type, prefix, next_number),
                )

        conn.commit()
        print("Done.")
        print("Clean testing accounts:")
        for code, name, acc_type in STANDARD_ACCOUNTS:
            print(f"- {code}: {name} ({acc_type})")
        print()
        print("Seed data:")
        print("- Customer: عميل اختبار")
        print("- Supplier: مورد اختبار")
        print("- Product: صنف اختبار | stock=100 | purchase=600 | sale=1000")
        print()
        print("Next step:")
        print("python safe_ultimate_test.py --mode FULL_SAFE")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
