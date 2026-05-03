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
    temp_dir = Path(tempfile.mkdtemp(prefix="erp-measurement-test-", dir=str(PROJECT_ROOT)))
    temp_db = temp_dir / "database_test.db"
    shutil.copy2(source_db, temp_db)

    old_db_path = appmod.DB_PATH
    old_module_db_path = appmod.MODULE_DEPS.get("DB_PATH")
    appmod.DB_PATH = str(temp_db)
    appmod.MODULE_DEPS["DB_PATH"] = str(temp_db)
    appmod.run_migrations(str(temp_db))
    appmod.init_db()
    appmod.app.config["TESTING"] = True

    client = appmod.app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = 1
        session["username"] = "measurement-test"
        session["role"] = "admin"

    conn = appmod.db()
    cur = conn.cursor()

    assert_true(fetchone(cur, "SELECT name FROM sqlite_master WHERE type='table' AND name='measurement_units'"), "measurement_units table missing")
    assert_true(fetchone(cur, "SELECT name FROM sqlite_master WHERE type='table' AND name='product_units'"), "product_units table missing")
    sales_line_columns = {row[1] for row in cur.execute("PRAGMA table_info(sales_invoice_lines)").fetchall()}
    purchase_line_columns = {row[1] for row in cur.execute("PRAGMA table_info(purchase_invoice_lines)").fetchall()}
    for expected_column in ("unit_id", "unit_name", "conversion_factor", "quantity_base"):
        assert_true(expected_column in sales_line_columns, f"missing sales_invoice_lines.{expected_column}")
        assert_true(expected_column in purchase_line_columns, f"missing purchase_invoice_lines.{expected_column}")

    add_unit_response = client.post(
        "/measurement-units/add",
        data={"name": "شريط", "code": "STRIP", "description": "وحدة اختبار"},
        follow_redirects=False,
    )
    assert_true(add_unit_response.status_code in (302, 303), "failed to add measurement unit")
    added_unit = fetchone(cur, "SELECT id,name FROM measurement_units WHERE code='STRIP'")
    assert_true(added_unit and added_unit[1] == "شريط", "measurement unit was not saved")

    product_create_response = client.post(
        "/products",
        data={
            "code": "UOM-TEST-01",
            "name": "دواء اختبار الوحدات",
            "unit": "وحدة",
            "purchase_price": "5",
            "sale_price": "8",
            "unit_row_index[]": ["0", "1"],
            "product_unit_id[]": [str(fetchone(cur, "SELECT id FROM measurement_units WHERE name='وحدة'")[0]), str(fetchone(cur, "SELECT id FROM measurement_units WHERE name='علبة'")[0])],
            "product_conversion_factor[]": ["1", "10"],
            "product_purchase_price[]": ["5", "45"],
            "product_sale_price[]": ["8", "70"],
            "product_barcode[]": ["", ""],
            "base_unit_row": "0",
            "default_purchase_row": "1",
            "default_sale_row": "1",
        },
        follow_redirects=False,
    )
    assert_true(product_create_response.status_code in (302, 303), "failed to create product with measurement units")
    product_id = fetchone(cur, "SELECT id FROM products WHERE code='UOM-TEST-01'")[0]
    product_unit_count = fetchone(cur, "SELECT COUNT(*) FROM product_units WHERE product_id=?", (product_id,))[0]
    assert_true(product_unit_count == 2, "product units were not linked to the product")

    cur.execute("INSERT INTO customers(name) VALUES ('عميل اختبار الوحدات')")
    customer_id = cur.lastrowid
    cur.execute("UPDATE products SET stock_quantity=240 WHERE id=?", (product_id,))
    conn.commit()

    box_unit_id = fetchone(
        cur,
        """
        SELECT pu.unit_id
        FROM product_units pu
        JOIN measurement_units mu ON mu.id=pu.unit_id
        WHERE pu.product_id=? AND mu.name='علبة'
        """,
        (product_id,),
    )[0]

    sale_response = client.post(
        "/sales",
        data={
            "date": "2026-05-03",
            "payment_type": "credit",
            "customer_id": str(customer_id),
            "due_date": "2026-05-05",
            "product_id": str(product_id),
            "unit_id": str(box_unit_id),
            "quantity": "2",
            "unit_price": "70",
            "tax_rate": "14",
            "po_ref": "",
            "gr_ref": "",
            "notes": "اختبار وحدات القياس",
        },
        follow_redirects=False,
    )
    assert_true(sale_response.status_code in (302, 303), "sale invoice failed with product unit")

    sales_invoice_id = fetchone(cur, "SELECT MAX(id) FROM sales_invoices")[0]
    sales_line = fetchone(
        cur,
        "SELECT unit_id,unit_name,conversion_factor,quantity,quantity_base,unit_price FROM sales_invoice_lines WHERE invoice_id=?",
        (sales_invoice_id,),
    )
    assert_true(sales_line is not None, "sales invoice line missing")
    assert_true(float(sales_line[2]) == 10.0, "conversion factor not stored on sales line")
    assert_true(float(sales_line[3]) == 2.0 and float(sales_line[4]) == 20.0, "base quantity conversion is incorrect")
    assert_true(float(fetchone(cur, "SELECT stock_quantity FROM products WHERE id=?", (product_id,))[0]) == 220.0, "stock was not reduced by base quantity")

    categories_response = client.get("/product-categories")
    measurement_units_response = client.get("/measurement-units")
    assert_true(categories_response.status_code == 200, "legacy /product-categories route failed")
    assert_true(measurement_units_response.status_code == 200, "measurement units screen failed")

    conn.close()
    appmod.DB_PATH = old_db_path
    appmod.MODULE_DEPS["DB_PATH"] = old_module_db_path
    shutil.rmtree(temp_dir, ignore_errors=True)
    print("measurement_units_test: ok")


if __name__ == "__main__":
    main()
