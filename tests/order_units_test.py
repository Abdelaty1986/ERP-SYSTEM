import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app as appmod


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def fetchone(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchone()


def main():
    source_db = PROJECT_ROOT / "database.db"
    temp_dir = Path(tempfile.mkdtemp(prefix="erp-order-units-test-", dir=str(PROJECT_ROOT)))
    temp_db = temp_dir / "database_test.db"
    shutil.copy2(source_db, temp_db)

    old_db_path = appmod.DB_PATH
    old_module_db_path = appmod.MODULE_DEPS.get("DB_PATH")
    appmod.DB_PATH = str(temp_db)
    appmod.MODULE_DEPS["DB_PATH"] = str(temp_db)
    appmod.init_db()
    appmod.app.config["TESTING"] = True

    client = appmod.app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = 1
        session["username"] = "codex-test"
        session["role"] = "admin"

    conn = appmod.db()
    cur = conn.cursor()

    cur.execute("INSERT INTO customers(name) VALUES (?)", ("عميل اختبار وحدات الأوامر",))
    customer_id = cur.lastrowid
    cur.execute("INSERT INTO suppliers(name) VALUES (?)", ("مورد اختبار وحدات الأوامر",))
    supplier_id = cur.lastrowid
    cur.execute(
        """
        INSERT INTO products(code,name,unit,purchase_price,sale_price,stock_quantity)
        VALUES (?,?,?,?,?,?)
        """,
        ("ORDER-UNIT-001", "صنف اختبار أوامر الوحدات", "قطعة", 5, 12, 200),
    )
    product_id = cur.lastrowid

    box_unit_id = fetchone(cur, "SELECT id FROM measurement_units WHERE name=?", ("علبة",))[0]
    carton_unit_id = fetchone(cur, "SELECT id FROM measurement_units WHERE name=?", ("كرتونة",))[0]
    cur.execute("DELETE FROM product_units WHERE product_id=?", (product_id,))
    cur.execute(
        """
        INSERT INTO product_units(
            product_id,unit_id,conversion_factor,purchase_price,sale_price,
            is_default_purchase,is_default_sale,is_base_unit,is_active
        )
        VALUES (?,?,?,?,?,1,0,1,1)
        """,
        (product_id, box_unit_id, 1, 5, 12),
    )
    cur.execute(
        """
        INSERT INTO product_units(
            product_id,unit_id,conversion_factor,purchase_price,sale_price,
            is_default_purchase,is_default_sale,is_base_unit,is_active
        )
        VALUES (?,?,?,?,?,0,1,0,1)
        """,
        (product_id, carton_unit_id, 12, 48, 120),
    )
    conn.commit()

    sales_order_resp = client.post(
        "/sales-orders",
        data={
            "date": "2026-05-03",
            "customer_id": str(customer_id),
            "delivery_date": "2026-05-03",
            "payment_terms": "اختبار",
            "notes": "اختبار وحدة أمر البيع",
            "product_id[]": [str(product_id)],
            "unit_id[]": [str(carton_unit_id)],
            "quantity[]": ["2"],
            "unit_price[]": ["120"],
            "tax_rate[]": ["14"],
        },
        follow_redirects=False,
    )
    assert_true(sales_order_resp.status_code in (302, 303), "فشل إنشاء أمر البيع بوحدة مخصصة")
    sales_order_line = fetchone(
        cur,
        "SELECT unit_id,unit_name,conversion_factor,quantity,quantity_base FROM sales_order_lines ORDER BY id DESC LIMIT 1",
    )
    assert_true(sales_order_line[0] == carton_unit_id, "لم يتم حفظ وحدة أمر البيع")
    assert_true(float(sales_order_line[2]) == 12.0 and float(sales_order_line[4]) == 24.0, "تحويل كمية أمر البيع غير صحيح")
    sales_order_line_id = fetchone(cur, "SELECT id FROM sales_order_lines ORDER BY id DESC LIMIT 1")[0]

    delivery_resp = client.post(
        "/sales-deliveries",
        data={
            "date": "2026-05-03",
            "sales_order_line_id": str(sales_order_line_id),
            "delivered_quantity": "2",
            "notes": "اختبار صرف أمر بيع بالوحدات",
        },
        follow_redirects=False,
    )
    assert_true(delivery_resp.status_code in (302, 303), "فشل إنشاء إذن صرف من أمر البيع")
    delivery_row = fetchone(
        cur,
        "SELECT unit_id,unit_name,conversion_factor,delivered_quantity,quantity_base FROM sales_delivery_notes ORDER BY id DESC LIMIT 1",
    )
    assert_true(delivery_row[0] == carton_unit_id and float(delivery_row[4]) == 24.0, "لم يتم ترحيل بيانات الوحدة إلى إذن الصرف")
    stock_after_delivery = fetchone(cur, "SELECT stock_quantity FROM products WHERE id=?", (product_id,))[0]
    assert_true(float(stock_after_delivery) == 176.0, "حركة مخزون إذن الصرف لم تستخدم الوحدة الأساسية")

    purchase_order_resp = client.post(
        "/purchase-orders",
        data={
            "date": "2026-05-03",
            "supplier_id": str(supplier_id),
            "payment_terms": "اختبار",
            "delivery_date": "2026-05-03",
            "delivery_terms": "اختبار",
            "notes": "اختبار وحدة أمر الشراء",
            "product_id[]": [str(product_id)],
            "unit_id[]": [str(carton_unit_id)],
            "quantity[]": ["1"],
            "unit_price[]": ["48"],
            "tax_rate[]": ["14"],
        },
        follow_redirects=False,
    )
    assert_true(purchase_order_resp.status_code in (302, 303), "فشل إنشاء أمر الشراء بوحدة مخصصة")
    purchase_order_line = fetchone(
        cur,
        "SELECT id,unit_id,unit_name,conversion_factor,quantity,quantity_base FROM purchase_order_lines ORDER BY id DESC LIMIT 1",
    )
    assert_true(purchase_order_line[1] == carton_unit_id and float(purchase_order_line[5]) == 12.0, "تحويل كمية أمر الشراء غير صحيح")

    receipt_resp = client.post(
        "/purchase-receipts",
        data={
            "date": "2026-05-03",
            "purchase_order_line_id": str(purchase_order_line[0]),
            "received_quantity": "1",
            "notes": "اختبار استلام أمر شراء بالوحدات",
        },
        follow_redirects=False,
    )
    assert_true(receipt_resp.status_code in (302, 303), "فشل إنشاء إذن استلام من أمر الشراء")
    receipt_row = fetchone(
        cur,
        "SELECT unit_id,unit_name,conversion_factor,received_quantity,quantity_base FROM purchase_receipts ORDER BY id DESC LIMIT 1",
    )
    assert_true(receipt_row[0] == carton_unit_id and float(receipt_row[4]) == 12.0, "لم يتم ترحيل بيانات الوحدة إلى إذن الاستلام")
    stock_after_receipt = fetchone(cur, "SELECT stock_quantity FROM products WHERE id=?", (product_id,))[0]
    assert_true(float(stock_after_receipt) == 188.0, "حركة مخزون إذن الاستلام لم تستخدم الوحدة الأساسية")

    appmod.DB_PATH = old_db_path
    appmod.MODULE_DEPS["DB_PATH"] = old_module_db_path
    conn.close()
    print("order_units_test: ok")


if __name__ == "__main__":
    main()
