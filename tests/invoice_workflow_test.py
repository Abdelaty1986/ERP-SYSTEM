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


def create_product(cur, code, name, purchase_price, sale_price, stock_quantity):
    cur.execute(
        """
        INSERT INTO products(code,name,unit,purchase_price,sale_price,stock_quantity)
        VALUES (?,?,?,?,?,?)
        """,
        (code, name, "وحدة", purchase_price, sale_price, stock_quantity),
    )
    return cur.lastrowid


def create_sales_order(cur, customer_id, lines):
    total = sum(line["quantity"] * line["unit_price"] for line in lines)
    cur.execute(
        """
        INSERT INTO sales_orders(
            date,customer_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total,payment_terms,delivery_date,notes,status
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("2026-05-03", customer_id, lines[0]["product_id"], total and lines[0]["quantity"], lines[0]["unit_price"], total, 14, 0, total, "cash", "2026-05-06", "sales order test", "issued"),
    )
    order_id = cur.lastrowid
    for line in lines:
        line_total = line["quantity"] * line["unit_price"]
        cur.execute(
            """
            INSERT INTO sales_order_lines(
                order_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total,unit_id,unit_name,conversion_factor,quantity_base
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (order_id, line["product_id"], line["quantity"], line["unit_price"], line_total, 14, 0, line_total, None, "وحدة", 1, line["quantity"]),
        )
    return order_id


def create_purchase_order(cur, supplier_id, lines):
    total = sum(line["quantity"] * line["unit_price"] for line in lines)
    cur.execute(
        """
        INSERT INTO purchase_orders(
            date,supplier_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total,payment_terms,delivery_date,delivery_terms,status,notes
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("2026-05-03", supplier_id, lines[0]["product_id"], total and lines[0]["quantity"], lines[0]["unit_price"], total, 14, 0, total, "cash", "2026-05-06", "", "draft", "purchase order test"),
    )
    order_id = cur.lastrowid
    for line in lines:
        line_total = line["quantity"] * line["unit_price"]
        cur.execute(
            """
            INSERT INTO purchase_order_lines(
                order_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total,unit_id,unit_name,conversion_factor,quantity_base
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (order_id, line["product_id"], line["quantity"], line["unit_price"], line_total, 14, 0, line_total, None, "وحدة", 1, line["quantity"]),
        )
    return order_id


def main():
    source_db = PROJECT_ROOT / "database.db"
    temp_dir = Path(tempfile.mkdtemp(prefix="erp-invoice-workflow-", dir=str(PROJECT_ROOT)))
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
        session["username"] = "invoice-workflow-test"
        session["role"] = "admin"

    conn = appmod.db()
    cur = conn.cursor()

    cur.execute("INSERT INTO customers(name) VALUES ('عميل اختبار فواتير')")
    customer_id = cur.lastrowid
    cur.execute("INSERT INTO suppliers(name) VALUES ('مورد اختبار فواتير')")
    supplier_id = cur.lastrowid

    sales_products = [
        create_product(cur, "SALE-WF-1", "صنف بيع 1", 10, 20, 100),
        create_product(cur, "SALE-WF-2", "صنف بيع 2", 11, 21, 100),
        create_product(cur, "SALE-WF-3", "صنف بيع 3", 12, 22, 100),
    ]
    purchase_products = [
        create_product(cur, "PUR-WF-1", "صنف شراء 1", 7, 14, 40),
        create_product(cur, "PUR-WF-2", "صنف شراء 2", 8, 15, 40),
        create_product(cur, "PUR-WF-3", "صنف شراء 3", 9, 16, 40),
    ]
    sales_order_products = [
        create_product(cur, "SO-WF-1", "صنف أمر بيع 1", 6, 18, 90),
        create_product(cur, "SO-WF-2", "صنف أمر بيع 2", 7, 19, 90),
        create_product(cur, "SO-WF-3", "صنف أمر بيع 3", 8, 20, 90),
    ]
    purchase_order_products = [
        create_product(cur, "PO-WF-1", "صنف أمر شراء 1", 5, 13, 30),
        create_product(cur, "PO-WF-2", "صنف أمر شراء 2", 6, 14, 30),
        create_product(cur, "PO-WF-3", "صنف أمر شراء 3", 7, 15, 30),
    ]
    conn.commit()

    direct_sale_response = client.post(
        "/sales",
        data={
            "date": "2026-05-03",
            "payment_type": "credit",
            "customer_id": str(customer_id),
            "due_date": "2026-05-10",
            "tax_rate": "14",
            "po_ref": "SO-DIRECT-REF",
            "gr_ref": "",
            "notes": "direct sales invoice",
            "product_id[]": [str(pid) for pid in sales_products],
            "quantity[]": ["1", "2", "3"],
            "unit_price[]": ["20", "21", "22"],
        },
        follow_redirects=False,
    )
    assert_true(direct_sale_response.status_code in (302, 303), "direct sales invoice request failed")

    sale_invoice = fetchone(cur, "SELECT id,doc_no,status FROM sales_invoices ORDER BY id DESC LIMIT 1")
    assert_true(sale_invoice is not None, "sales invoice header missing")
    sale_invoice_id, sale_doc_no, sale_status = sale_invoice
    assert_true(sale_status == "posted", "direct sales invoice should be posted once")
    assert_true(fetchone(cur, "SELECT COUNT(*) FROM sales_invoice_lines WHERE invoice_id=?", (sale_invoice_id,))[0] == 3, "direct sales invoice should have 3 lines")
    assert_true(fetchone(cur, "SELECT COUNT(*) FROM inventory_movements WHERE reference_type='sale' AND reference_id=?", (sale_invoice_id,))[0] == 3, "direct sales invoice should create 3 stock movements")
    assert_true(fetchone(cur, "SELECT COUNT(*) FROM journal WHERE source_type='sales' AND source_id=?", (sale_invoice_id,))[0] >= 1, "direct sales invoice journals missing")
    expected_sales_stock = {sales_products[0]: 99.0, sales_products[1]: 98.0, sales_products[2]: 97.0}
    for product_id, expected_stock in expected_sales_stock.items():
        current_stock = float(fetchone(cur, "SELECT stock_quantity FROM products WHERE id=?", (product_id,))[0])
        assert_true(current_stock == expected_stock, f"unexpected stock after direct sales invoice for product {product_id}")

    sale_create_page = client.get("/sales")
    sale_list_page = client.get("/sales/invoices")
    assert_true(sale_create_page.status_code == 200, "sales create page failed")
    assert_true(sale_list_page.status_code == 200, "sales invoices list page failed")
    assert_true(sale_doc_no not in sale_create_page.get_data(as_text=True), "sales create page should not show previous invoices")
    assert_true(sale_doc_no in sale_list_page.get_data(as_text=True), "sales invoices list page should show previous invoices")

    sale_journal_count = fetchone(cur, "SELECT COUNT(*) FROM journal WHERE source_type='sales' AND source_id=?", (sale_invoice_id,))[0]
    sale_move_count = fetchone(cur, "SELECT COUNT(*) FROM inventory_movements WHERE reference_type='sale' AND reference_id=?", (sale_invoice_id,))[0]
    appmod.post_sales_invoice(cur, sale_invoice_id)
    assert_true(fetchone(cur, "SELECT COUNT(*) FROM journal WHERE source_type='sales' AND source_id=?", (sale_invoice_id,))[0] == sale_journal_count, "sales invoice was posted twice")
    assert_true(fetchone(cur, "SELECT COUNT(*) FROM inventory_movements WHERE reference_type='sale' AND reference_id=?", (sale_invoice_id,))[0] == sale_move_count, "sales stock was posted twice")

    direct_purchase_response = client.post(
        "/purchases",
        data={
            "date": "2026-05-03",
            "supplier_invoice_no": "SUP-INV-WF-1",
            "supplier_invoice_date": "2026-05-03",
            "payment_type": "credit",
            "supplier_id": str(supplier_id),
            "due_date": "2026-05-10",
            "tax_rate": "14",
            "notes": "direct purchase invoice",
            "product_id[]": [str(pid) for pid in purchase_products],
            "quantity[]": ["1", "2", "3"],
            "unit_price[]": ["17", "18", "19"],
        },
        follow_redirects=False,
    )
    assert_true(direct_purchase_response.status_code in (302, 303), "direct purchase invoice request failed")

    purchase_invoice = fetchone(cur, "SELECT id,doc_no,status FROM purchase_invoices ORDER BY id DESC LIMIT 1")
    assert_true(purchase_invoice is not None, "purchase invoice header missing")
    purchase_invoice_id, purchase_doc_no, purchase_status = purchase_invoice
    assert_true(purchase_status == "posted", "direct purchase invoice should be posted once")
    assert_true(fetchone(cur, "SELECT COUNT(*) FROM purchase_invoice_lines WHERE invoice_id=?", (purchase_invoice_id,))[0] == 3, "direct purchase invoice should have 3 lines")
    assert_true(fetchone(cur, "SELECT COUNT(*) FROM inventory_movements WHERE reference_type='purchase' AND reference_id=?", (purchase_invoice_id,))[0] == 3, "direct purchase invoice should create 3 stock movements")
    assert_true(fetchone(cur, "SELECT COUNT(*) FROM journal WHERE source_type='purchases' AND source_id=?", (purchase_invoice_id,))[0] >= 1, "direct purchase invoice journals missing")
    expected_purchase_stock = {purchase_products[0]: 41.0, purchase_products[1]: 42.0, purchase_products[2]: 43.0}
    for product_id, expected_stock in expected_purchase_stock.items():
        current_stock = float(fetchone(cur, "SELECT stock_quantity FROM products WHERE id=?", (product_id,))[0])
        assert_true(current_stock == expected_stock, f"unexpected stock after direct purchase invoice for product {product_id}")

    purchase_create_page = client.get("/purchases")
    purchase_list_page = client.get("/purchases/invoices")
    assert_true(purchase_create_page.status_code == 200, "purchase create page failed")
    assert_true(purchase_list_page.status_code == 200, "purchase invoices list page failed")
    assert_true(purchase_doc_no not in purchase_create_page.get_data(as_text=True), "purchase create page should not show previous invoices")
    assert_true(purchase_doc_no in purchase_list_page.get_data(as_text=True), "purchase invoices list page should show previous invoices")

    purchase_journal_count = fetchone(cur, "SELECT COUNT(*) FROM journal WHERE source_type='purchases' AND source_id=?", (purchase_invoice_id,))[0]
    purchase_move_count = fetchone(cur, "SELECT COUNT(*) FROM inventory_movements WHERE reference_type='purchase' AND reference_id=?", (purchase_invoice_id,))[0]
    appmod.post_purchase_invoice(cur, purchase_invoice_id)
    assert_true(fetchone(cur, "SELECT COUNT(*) FROM journal WHERE source_type='purchases' AND source_id=?", (purchase_invoice_id,))[0] == purchase_journal_count, "purchase invoice was posted twice")
    assert_true(fetchone(cur, "SELECT COUNT(*) FROM inventory_movements WHERE reference_type='purchase' AND reference_id=?", (purchase_invoice_id,))[0] == purchase_move_count, "purchase stock was posted twice")

    sales_order_lines = [
        {"product_id": sales_order_products[0], "quantity": 1, "unit_price": 18},
        {"product_id": sales_order_products[1], "quantity": 2, "unit_price": 19},
        {"product_id": sales_order_products[2], "quantity": 3, "unit_price": 20},
    ]
    purchase_order_lines = [
        {"product_id": purchase_order_products[0], "quantity": 1, "unit_price": 11},
        {"product_id": purchase_order_products[1], "quantity": 2, "unit_price": 12},
        {"product_id": purchase_order_products[2], "quantity": 3, "unit_price": 13},
    ]
    sales_order_id = create_sales_order(cur, customer_id, sales_order_lines)
    purchase_order_id = create_purchase_order(cur, supplier_id, purchase_order_lines)
    conn.commit()

    convert_sales_order_response = client.post(
        "/sales",
        data={
            "sales_order_id": str(sales_order_id),
            "date": "2026-05-04",
            "payment_type": "credit",
            "customer_id": str(customer_id),
            "due_date": "2026-05-11",
            "tax_rate": "14",
            "po_ref": "",
            "gr_ref": "",
            "notes": "converted sales order",
        },
        follow_redirects=False,
    )
    assert_true(convert_sales_order_response.status_code in (302, 303), "sales order conversion failed")
    converted_sales = fetchone(cur, "SELECT id,sales_order_id,status FROM sales_invoices WHERE sales_order_id=? ORDER BY id DESC LIMIT 1", (sales_order_id,))
    assert_true(converted_sales is not None, "converted sales order header missing")
    assert_true(converted_sales[1] == sales_order_id, "sales order id was not stored on invoice header")
    assert_true(converted_sales[2] == "posted", "converted sales order invoice should be posted")
    assert_true(fetchone(cur, "SELECT COUNT(*) FROM sales_invoice_lines WHERE invoice_id=?", (converted_sales[0],))[0] == 3, "sales order conversion should create one invoice with 3 lines")

    convert_sales_order_again = client.post(
        "/sales",
        data={
            "sales_order_id": str(sales_order_id),
            "date": "2026-05-04",
            "payment_type": "credit",
            "customer_id": str(customer_id),
            "due_date": "2026-05-11",
            "tax_rate": "14",
        },
        follow_redirects=False,
    )
    assert_true(convert_sales_order_again.status_code in (302, 303), "duplicate sales order conversion should redirect safely")
    assert_true(fetchone(cur, "SELECT COUNT(*) FROM sales_invoices WHERE sales_order_id=?", (sales_order_id,))[0] == 1, "sales order was converted more than once")

    convert_purchase_order_response = client.post(
        "/purchases",
        data={
            "purchase_order_id": str(purchase_order_id),
            "date": "2026-05-04",
            "supplier_invoice_no": "SUP-INV-WF-PO",
            "supplier_invoice_date": "2026-05-04",
            "payment_type": "credit",
            "supplier_id": str(supplier_id),
            "due_date": "2026-05-11",
            "tax_rate": "14",
            "notes": "converted purchase order",
        },
        follow_redirects=False,
    )
    assert_true(convert_purchase_order_response.status_code in (302, 303), "purchase order conversion failed")
    converted_purchase = fetchone(cur, "SELECT id,purchase_order_id,status FROM purchase_invoices WHERE purchase_order_id=? ORDER BY id DESC LIMIT 1", (purchase_order_id,))
    assert_true(converted_purchase is not None, "converted purchase order header missing")
    assert_true(converted_purchase[1] == purchase_order_id, "purchase order id was not stored on invoice header")
    assert_true(converted_purchase[2] == "posted", "converted purchase order invoice should be posted")
    assert_true(fetchone(cur, "SELECT COUNT(*) FROM purchase_invoice_lines WHERE invoice_id=?", (converted_purchase[0],))[0] == 3, "purchase order conversion should create one invoice with 3 lines")

    convert_purchase_order_again = client.post(
        "/purchases",
        data={
            "purchase_order_id": str(purchase_order_id),
            "date": "2026-05-04",
            "supplier_invoice_no": "SUP-INV-WF-PO-2",
            "supplier_invoice_date": "2026-05-04",
            "payment_type": "credit",
            "supplier_id": str(supplier_id),
            "due_date": "2026-05-11",
            "tax_rate": "14",
        },
        follow_redirects=False,
    )
    assert_true(convert_purchase_order_again.status_code in (302, 303), "duplicate purchase order conversion should redirect safely")
    assert_true(fetchone(cur, "SELECT COUNT(*) FROM purchase_invoices WHERE purchase_order_id=?", (purchase_order_id,))[0] == 1, "purchase order was converted more than once")

    conn.rollback()
    conn.close()
    appmod.DB_PATH = old_db_path
    appmod.MODULE_DEPS["DB_PATH"] = old_module_db_path
    shutil.rmtree(temp_dir, ignore_errors=True)
    print("invoice_workflow_test: ok")


if __name__ == "__main__":
    main()
