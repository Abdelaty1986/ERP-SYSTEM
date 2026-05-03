import shutil
import sys
import tempfile
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app as appmod


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def find_header_row(sheet):
    """
    يبحث عن صف الأعمدة الحقيقي وليس عنوان التقرير
    """
    for i in range(1, 30):
        row_values = []
        for cell in sheet[i]:
            if cell.value is not None:
                row_values.append(str(cell.value).strip())

        joined = " | ".join(row_values)

        if (
            ("كمية" in joined or "الكمية" in joined)
            and ("سعر" in joined)
            and ("وحدة" in joined)
        ):
            return i, row_values

    # fallback: أطول صف بعد العنوان
    best_row = []
    best_index = None
    for i in range(3, 30):
        row_values = [str(cell.value).strip() for cell in sheet[i] if cell.value is not None]
        if len(row_values) > len(best_row):
            best_row = row_values
            best_index = i

    return best_index, best_row


def main():
    print("Running VAT report validation...")

    # قاعدة مؤقتة
    source_db = PROJECT_ROOT / "database.db"
    temp_dir = Path(tempfile.mkdtemp(prefix="erp-test-", dir=str(PROJECT_ROOT)))
    temp_db = temp_dir / "database_test.db"
    shutil.copy2(source_db, temp_db)

    old_db_path = appmod.DB_PATH
    appmod.DB_PATH = str(temp_db)
    appmod.run_migrations(str(temp_db))
    appmod.init_db()

    appmod.app.config["TESTING"] = True
    client = appmod.app.test_client()

    with client.session_transaction() as session:
        session["user_id"] = 1
        session["role"] = "admin"

    conn = appmod.db()
    cur = conn.cursor()

    # بيانات اختبار
    cur.execute("INSERT INTO customers(name,tax_id) VALUES (?,?)", ("عميل اختبار", "TAX123"))
    customer_id = cur.lastrowid

    cur.execute(
        "INSERT INTO products(code,name,unit,purchase_price,sale_price,stock_quantity) VALUES (?,?,?,?,?,?)",
        ("TEST1", "صنف اختبار", "علبة", 10, 20, 100),
    )
    product_id = cur.lastrowid
    conn.commit()

    # إنشاء فاتورة
    client.post(
        "/sales",
        data={
            "date": "2026-05-01",
            "invoice_number": "INV-TEST-1",
            "product_id[]": [str(product_id)],
            "quantity[]": ["2"],
            "unit_price[]": ["20"],
        },
    )

    # تحميل تقرير VAT من السيرفر
    response = client.get("/reports/vat?format=excel")
    assert_true(response.status_code == 200, "VAT report export failed")

    wb = load_workbook(BytesIO(response.data))
    sheet = wb.active

    row_index, headers = find_header_row(sheet)

    print("Detected Headers:", headers)

    # التحقق
    assert_true(any("كمية" in h for h in headers), "Missing quantity")
    assert_true(any("سعر" in h for h in headers), "Missing unit price")
    assert_true(any("وحدة" in h for h in headers), "Missing unit")
    assert_true(any("ضريبي" in h for h in headers), "Missing tax number")

    print("VAT report test passed successfully")


if __name__ == "__main__":
    main()