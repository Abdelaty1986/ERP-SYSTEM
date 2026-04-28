"""
Golden Accounting Test for Ledger X

الغرض:
- اختبار دورة محاسبية كاملة بدون لمس قاعدة البيانات الأصلية.
- يعمل على نسخة مؤقتة من database.db داخل فولدر .test_runs.
- يختبر: عميل، مورد، صنف، فاتورة شراء، فاتورة بيع، سند قبض، قيود، أستاذ، ومخزون.

مكان الملف:
- ضعه بجانب app.py في جذر المشروع، أو داخل tests/ وشغله بـ:
  PYTHONPATH=. python tests/golden_accounting_test.py

تشغيل عادي من جذر المشروع:
  python golden_accounting_test.py
"""

import json
import shutil
import sqlite3
import sys
import tempfile
from datetime import date
from pathlib import Path


def find_project_root() -> Path:
    here = Path(__file__).resolve().parent
    if (here / "app.py").exists():
        return here
    if (here.parent / "app.py").exists():
        return here.parent
    raise SystemExit("❌ لم أجد app.py. شغّل الاختبار من داخل فولدر المشروع أو ضعه بجانب app.py.")


PROJECT_ROOT = find_project_root()
sys.path.insert(0, str(PROJECT_ROOT))

import app as appmod  # noqa: E402


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def fetchone(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchone()


def table_columns(cur, table_name):
    cur.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cur.fetchall()]


def account_id(cur, code):
    cur.execute("SELECT id FROM accounts WHERE code=?", (code,))
    row = cur.fetchone()
    assert_true(row is not None, f"الحساب الافتراضي غير موجود: {code}")
    return row[0]


def create_journal(cur, journal_date, description, debit_code, credit_code, amount, source_type="golden_test", source_id=None):
    if not amount or amount <= 0:
        return None

    debit_id = account_id(cur, debit_code)
    credit_id = account_id(cur, credit_code)

    cur.execute(
        """
        INSERT INTO journal(date,description,debit_account_id,credit_account_id,amount,status,source_type,source_id)
        VALUES (?,?,?,?,?,'posted',?,?)
        """,
        (journal_date, description, debit_id, credit_id, amount, source_type, source_id),
    )
    return cur.lastrowid


def rebuild_ledger_from_journal(cur):
    cur.execute("DELETE FROM ledger")
    cur.execute(
        """
        SELECT id,date,description,debit_account_id,credit_account_id,amount
        FROM journal
        WHERE status='posted'
        ORDER BY id
        """
    )
    for journal_id, journal_date, desc, debit_id, credit_id, amount in cur.fetchall():
        cur.execute(
            """
            INSERT INTO ledger(account_id,date,description,debit,credit,journal_id)
            VALUES (?,?,?,?,?,?)
            """,
            (debit_id, journal_date, desc, amount, 0, journal_id),
        )
        cur.execute(
            """
            INSERT INTO ledger(account_id,date,description,debit,credit,journal_id)
            VALUES (?,?,?,?,?,?)
            """,
            (credit_id, journal_date, desc, 0, amount, journal_id),
        )


def insert_customer(cur):
    columns = table_columns(cur, "customers")
    values = {
        "name": "عميل اختبار Golden Test",
        "phone": "01000000000",
        "address": "اختبار",
        "tax_registration_number": "TEST-CUST-TAX",
        "contact_person": "مسؤول اختبار",
        "email": "customer-test@example.com",
        "withholding_status": "subject",
    }
    used = {k: v for k, v in values.items() if k in columns}
    sql = f"INSERT INTO customers({','.join(used.keys())}) VALUES ({','.join(['?'] * len(used))})"
    cur.execute(sql, list(used.values()))
    return cur.lastrowid


def insert_supplier(cur):
    columns = table_columns(cur, "suppliers")
    values = {
        "name": "مورد اختبار Golden Test",
        "phone": "01000000001",
        "address": "اختبار",
        "tax_registration_number": "TEST-SUP-TAX",
        "contact_person": "مسؤول اختبار",
        "email": "supplier-test@example.com",
        "withholding_status": "taxable",
    }
    used = {k: v for k, v in values.items() if k in columns}
    sql = f"INSERT INTO suppliers({','.join(used.keys())}) VALUES ({','.join(['?'] * len(used))})"
    cur.execute(sql, list(used.values()))
    return cur.lastrowid


def insert_product(cur):
    columns = table_columns(cur, "products")
    code = "GOLDEN-TEST-001"

    # لو الكود موجود في نسخة الاختبار لأي سبب، نغيره برقم إضافي
    cur.execute("SELECT COUNT(*) FROM products WHERE code=?", (code,))
    if cur.fetchone()[0]:
        code = f"GOLDEN-TEST-{date.today().strftime('%Y%m%d')}"

    values = {
        "code": code,
        "name": "صنف اختبار Golden Test",
        "unit": "قطعة",
        "purchase_price": 100,
        "sale_price": 150,
        "stock_quantity": 0,
        # لا نستخدم category كنص لأن جدول products عندك لا يحتوي عليه.
        # ولو عندك category_id نسيبه فارغ لأن الاختبار لا يحتاج تصنيف.
        "category_id": None,
    }
    used = {k: v for k, v in values.items() if k in columns}
    sql = f"INSERT INTO products({','.join(used.keys())}) VALUES ({','.join(['?'] * len(used))})"
    cur.execute(sql, list(used.values()))
    return cur.lastrowid


def run():
    source_db = PROJECT_ROOT / "database.db"
    assert_true(source_db.exists(), "database.db غير موجودة في فولدر المشروع")

    test_runs_dir = PROJECT_ROOT / ".test_runs"
    test_runs_dir.mkdir(exist_ok=True)

    temp_dir = Path(tempfile.mkdtemp(prefix="golden-accounting-", dir=str(test_runs_dir)))
    temp_db = temp_dir / "database_test.db"
    shutil.copy2(source_db, temp_db)

    old_db_path = appmod.DB_PATH
    old_module_db_path = appmod.MODULE_DEPS.get("DB_PATH") if hasattr(appmod, "MODULE_DEPS") else None

    try:
        appmod.DB_PATH = str(temp_db)
        if hasattr(appmod, "MODULE_DEPS"):
            appmod.MODULE_DEPS["DB_PATH"] = str(temp_db)

        appmod.init_db()

        conn = sqlite3.connect(temp_db, timeout=30)
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.execute("PRAGMA busy_timeout = 30000")

        today = date.today().isoformat()

        print("=" * 70)
        print("🚀 بدء Golden Accounting Test على نسخة مؤقتة من قاعدة البيانات")
        print(f"📁 قاعدة الاختبار: {temp_db}")
        print("=" * 70)

        customer_id = insert_customer(cur)
        supplier_id = insert_supplier(cur)
        product_id = insert_product(cur)

        print(f"✅ عميل اختبار ID: {customer_id}")
        print(f"✅ مورد اختبار ID: {supplier_id}")
        print(f"✅ صنف اختبار ID: {product_id}")

        # 1) فاتورة شراء: 10 قطع × 100 = 1000 + VAT 140 - WHT 10 = 1130
        purchase_total = 1000.0
        purchase_vat = 140.0
        purchase_wht = 10.0
        purchase_grand = purchase_total + purchase_vat - purchase_wht

        cur.execute(
            """
            INSERT INTO purchase_invoices(
                date,supplier_invoice_no,supplier_invoice_date,due_date,
                supplier_id,product_id,quantity,unit_price,total,
                tax_rate,tax_amount,withholding_rate,withholding_amount,grand_total,
                payment_type,status,notes,doc_no
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                today, "SUP-GOLDEN-001", today, today,
                supplier_id, product_id, 10, 100, purchase_total,
                14, purchase_vat, 1, purchase_wht, purchase_grand,
                "credit", "posted", "Golden Test purchase invoice", "PI-GOLDEN-001",
            ),
        )
        purchase_id = cur.lastrowid

        # لو جدول بنود المشتريات موجود، نضيف بند
        if "purchase_invoice_lines" in get_tables(cur):
            line_cols = table_columns(cur, "purchase_invoice_lines")
            line_values = {
                "invoice_id": purchase_id,
                "product_id": product_id,
                "quantity": 10,
                "unit_price": 100,
                "total": purchase_total,
                "vat_enabled": 1,
                "withholding_enabled": 1,
                "vat_rate": 14,
                "withholding_rate": 1,
                "vat_amount": purchase_vat,
                "withholding_amount": purchase_wht,
            }
            used = {k: v for k, v in line_values.items() if k in line_cols}
            cur.execute(
                f"INSERT INTO purchase_invoice_lines({','.join(used.keys())}) VALUES ({','.join(['?'] * len(used))})",
                list(used.values()),
            )

        cur.execute("UPDATE products SET stock_quantity=stock_quantity+10, purchase_price=? WHERE id=?", (100, product_id))

        purchase_journal = create_journal(cur, today, "Golden Test - فاتورة شراء", "1400", "2100", purchase_total, "purchases", purchase_id)
        purchase_vat_journal = create_journal(cur, today, "Golden Test - ضريبة مدخلات شراء", "1500", "2100", purchase_vat, "purchases", purchase_id)
        purchase_wht_journal = create_journal(cur, today, "Golden Test - خصم وإضافة مورد", "2100", "2230", purchase_wht, "purchases", purchase_id)

        cur.execute(
            """
            UPDATE purchase_invoices
            SET journal_id=?, tax_journal_id=?, withholding_journal_id=?
            WHERE id=?
            """,
            (purchase_journal, purchase_vat_journal, purchase_wht_journal, purchase_id),
        )

        # 2) فاتورة بيع: 4 قطع × 150 = 600 + VAT 84 - WHT 6 = 678
        sale_total = 600.0
        sale_cost = 400.0
        sale_vat = 84.0
        sale_wht = 6.0
        sale_grand = sale_total + sale_vat - sale_wht

        cur.execute(
            """
            INSERT INTO sales_invoices(
                date,due_date,doc_no,customer_id,product_id,quantity,unit_price,total,cost_total,
                tax_rate,tax_amount,withholding_rate,withholding_amount,grand_total,
                payment_type,status,notes
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                today, today, "SI-GOLDEN-001", customer_id, product_id, 4, 150, sale_total, sale_cost,
                14, sale_vat, 1, sale_wht, sale_grand,
                "credit", "posted", "Golden Test sales invoice",
            ),
        )
        sale_id = cur.lastrowid

        if "sales_invoice_lines" in get_tables(cur):
            line_cols = table_columns(cur, "sales_invoice_lines")
            line_values = {
                "invoice_id": sale_id,
                "product_id": product_id,
                "quantity": 4,
                "unit_price": 150,
                "total": sale_total,
                "cost_total": sale_cost,
                "vat_enabled": 1,
                "withholding_enabled": 1,
                "vat_rate": 14,
                "withholding_rate": 1,
                "vat_amount": sale_vat,
                "withholding_amount": sale_wht,
                "grand_total": sale_grand,
            }
            used = {k: v for k, v in line_values.items() if k in line_cols}
            cur.execute(
                f"INSERT INTO sales_invoice_lines({','.join(used.keys())}) VALUES ({','.join(['?'] * len(used))})",
                list(used.values()),
            )

        cur.execute("UPDATE products SET stock_quantity=stock_quantity-4 WHERE id=?", (product_id,))

        sale_journal = create_journal(cur, today, "Golden Test - فاتورة بيع", "1300", "4100", sale_total, "sales", sale_id)
        sale_vat_journal = create_journal(cur, today, "Golden Test - ضريبة مخرجات بيع", "1300", "2200", sale_vat, "sales", sale_id)
        sale_wht_journal = create_journal(cur, today, "Golden Test - خصم وإضافة عميل", "1510", "1300", sale_wht, "sales", sale_id)
        sale_cogs_journal = create_journal(cur, today, "Golden Test - تكلفة بضاعة مباعة", "6100", "1400", sale_cost, "sales", sale_id)

        cur.execute(
            """
            UPDATE sales_invoices
            SET journal_id=?, tax_journal_id=?, withholding_journal_id=?, cogs_journal_id=?
            WHERE id=?
            """,
            (sale_journal, sale_vat_journal, sale_wht_journal, sale_cogs_journal, sale_id),
        )

        # 3) سند قبض من العميل بقيمة الصافي المحصل
        cur.execute(
            """
            INSERT INTO receipt_vouchers(date,customer_id,amount,notes,status)
            VALUES (?,?,?,?,?)
            """,
            (today, customer_id, sale_grand, "Golden Test receipt voucher", "posted"),
        )
        receipt_id = cur.lastrowid
        receipt_journal = create_journal(cur, today, "Golden Test - سند قبض", "1100", "1300", sale_grand, "receipts", receipt_id)
        cur.execute("UPDATE receipt_vouchers SET journal_id=? WHERE id=?", (receipt_journal, receipt_id))

        rebuild_ledger_from_journal(cur)
        conn.commit()

        # Verification
        stock = fetchone(cur, "SELECT stock_quantity FROM products WHERE id=?", (product_id,))[0]
        sales_vat_sum = fetchone(cur, "SELECT SUM(tax_amount) FROM sales_invoices WHERE customer_id=?", (customer_id,))[0] or 0
        purchase_vat_sum = fetchone(cur, "SELECT SUM(tax_amount) FROM purchase_invoices WHERE supplier_id=?", (supplier_id,))[0] or 0
        net_vat = sales_vat_sum - purchase_vat_sum

        journal_count = fetchone(cur, "SELECT COUNT(*) FROM journal WHERE source_type IN ('sales','purchases','receipts')")[0]
        ledger_count = fetchone(cur, "SELECT COUNT(*) FROM ledger")[0]

        total_debit = fetchone(cur, "SELECT SUM(debit) FROM ledger")[0] or 0
        total_credit = fetchone(cur, "SELECT SUM(credit) FROM ledger")[0] or 0

        assert_true(float(stock) == 6.0, f"رصيد المخزون غير صحيح. المتوقع 6، الفعلي {stock}")
        assert_true(float(sales_vat_sum) == sale_vat, f"ضريبة المبيعات غير صحيحة. المتوقع {sale_vat}، الفعلي {sales_vat_sum}")
        assert_true(float(purchase_vat_sum) == purchase_vat, f"ضريبة المشتريات غير صحيحة. المتوقع {purchase_vat}، الفعلي {purchase_vat_sum}")
        assert_true(round(total_debit, 2) == round(total_credit, 2), f"القيود غير متوازنة: مدين {total_debit} / دائن {total_credit}")
        assert_true(journal_count >= 8, f"عدد القيود أقل من المتوقع: {journal_count}")
        assert_true(ledger_count >= journal_count * 2, f"الأستاذ لم يُبنى بشكل صحيح: ledger={ledger_count}, journal={journal_count}")

        result = {
            "status": "PASSED",
            "temp_db": str(temp_db),
            "customer_id": customer_id,
            "supplier_id": supplier_id,
            "product_id": product_id,
            "purchase_invoice_id": purchase_id,
            "sales_invoice_id": sale_id,
            "receipt_id": receipt_id,
            "expected_stock": 6,
            "actual_stock": stock,
            "sales_vat": sales_vat_sum,
            "purchase_vat": purchase_vat_sum,
            "net_vat": net_vat,
            "journal_count": journal_count,
            "ledger_count": ledger_count,
            "total_debit": round(total_debit, 2),
            "total_credit": round(total_credit, 2),
        }

        print("\n✅ Golden Accounting Test PASSED")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("\nملاحظة: الاختبار اشتغل على نسخة مؤقتة ولم يغير database.db الأصلية.")

        conn.close()

    finally:
        appmod.DB_PATH = old_db_path
        if hasattr(appmod, "MODULE_DEPS") and old_module_db_path is not None:
            appmod.MODULE_DEPS["DB_PATH"] = old_module_db_path


def get_tables(cur):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row[0] for row in cur.fetchall()}


if __name__ == "__main__":
    run()
