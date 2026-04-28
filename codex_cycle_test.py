import json
import shutil
import tempfile
from pathlib import Path

import app as appmod


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def fetchone(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchone()


def main():
    workspace = Path(__file__).resolve().parent
    source_db = workspace / "database.db"
    temp_dir = Path(tempfile.mkdtemp(prefix="erp-codex-test-", dir=str(workspace)))
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

    customer_name = "عميل اختبار كودكس"
    supplier_name = "مورد اختبار كودكس"
    product_name = "صنف اختبار كودكس"

    cur.execute("INSERT INTO customers(name) VALUES (?)", (customer_name,))
    customer_id = cur.lastrowid
    cur.execute("INSERT INTO suppliers(name) VALUES (?)", (supplier_name,))
    supplier_id = cur.lastrowid
    cur.execute(
        """
        INSERT INTO products(code,name,unit,purchase_price,sale_price,stock_quantity)
        VALUES (?,?,?,?,?,?)
        """,
        ("CODEX-TEST", product_name, "قطعة", 40, 100, 100),
    )
    product_id = cur.lastrowid
    conn.commit()

    sales_order_resp = client.post(
        "/sales-orders",
        data={
            "date": "2026-04-28",
            "customer_id": str(customer_id),
            "delivery_date": "2026-04-28",
            "payment_terms": "اختبار",
            "notes": "اختبار دورة المبيعات",
            "product_id[]": [str(product_id)],
            "quantity[]": ["5"],
            "unit_price[]": ["100"],
            "tax_rate[]": ["14"],
        },
        follow_redirects=False,
    )
    assert_true(sales_order_resp.status_code in (302, 303), "فشل إنشاء أمر البيع")
    sales_order_id = fetchone(cur, "SELECT MAX(id) FROM sales_orders")[0]
    sales_order_line_id = fetchone(cur, "SELECT id FROM sales_order_lines WHERE order_id=?", (sales_order_id,))[0]

    delivery_resp = client.post(
        "/sales-deliveries",
        data={
            "date": "2026-04-28",
            "sales_order_line_id": str(sales_order_line_id),
            "delivered_quantity": "5",
            "notes": "اختبار إذن صرف",
        },
        follow_redirects=False,
    )
    assert_true(delivery_resp.status_code in (302, 303), "فشل إنشاء إذن الصرف")
    delivery_id = fetchone(cur, "SELECT MAX(id) FROM sales_delivery_notes")[0]
    stock_after_delivery = fetchone(cur, "SELECT stock_quantity FROM products WHERE id=?", (product_id,))[0]
    assert_true(float(stock_after_delivery) == 95, "أثر المخزون بعد إذن الصرف غير صحيح")

    sales_invoice_resp = client.post(
        "/sales/from-delivery",
        data={
            "date": "2026-04-28",
            "due_date": "2026-04-30",
            "payment_type": "credit",
            "po_ref": "PO-SALES-TEST",
            "gr_ref": "GR-SALES-TEST",
            "notes": "اختبار فاتورة من إذن صرف",
            "delivery_ids": [str(delivery_id)],
            f"vat_enabled_{delivery_id}": "1",
            f"vat_rate_{delivery_id}": "14",
        },
        follow_redirects=False,
    )
    assert_true(sales_invoice_resp.status_code in (302, 303), "فشل إنشاء فاتورة البيع من إذن الصرف")
    sales_invoice_id = fetchone(cur, "SELECT MAX(id) FROM sales_invoices")[0]
    sales_invoice = fetchone(cur, "SELECT quantity,unit_price,total,status FROM sales_invoices WHERE id=?", (sales_invoice_id,))
    assert_true(tuple(map(float, sales_invoice[:3])) == (5.0, 100.0, 500.0), "بيانات الكمية/السعر/الإجمالي في فاتورة البيع غير صحيحة")
    assert_true(sales_invoice[3] == "posted", "حالة فاتورة البيع غير صحيحة")
    sales_line = fetchone(cur, "SELECT quantity,unit_price,total FROM sales_invoice_lines WHERE invoice_id=?", (sales_invoice_id,))
    assert_true(tuple(map(float, sales_line)) == (5.0, 100.0, 500.0), "بيانات بند فاتورة البيع غير صحيحة")
    delivery_row = fetchone(cur, "SELECT status,invoice_id FROM sales_delivery_notes WHERE id=?", (delivery_id,))
    assert_true(delivery_row == ("invoiced", sales_invoice_id), "إذن الصرف لم يتحول إلى مفوتر")

    sale_print = client.get(f"/sales/{sales_invoice_id}/print")
    sale_excel = client.get(f"/sales/{sales_invoice_id}/export")
    assert_true(sale_print.status_code == 200, "طباعة فاتورة البيع فشلت")
    assert_true(sale_excel.status_code == 200, "تصدير Excel لفاتورة البيع فشل")

    cancel_sale_resp = client.post(
        f"/sales/{sales_invoice_id}/cancel",
        data={"reason": "اختبار إلغاء فاتورة بيع"},
        follow_redirects=False,
    )
    assert_true(cancel_sale_resp.status_code in (302, 303), "فشل إلغاء فاتورة البيع")
    cancelled_invoice = fetchone(cur, "SELECT status FROM sales_invoices WHERE id=?", (sales_invoice_id,))[0]
    cancelled_delivery = fetchone(cur, "SELECT status,invoice_id FROM sales_delivery_notes WHERE id=?", (delivery_id,))
    stock_after_sale_cancel = fetchone(cur, "SELECT stock_quantity FROM products WHERE id=?", (product_id,))[0]
    sales_order_status = fetchone(cur, "SELECT status FROM sales_orders WHERE id=?", (sales_order_id,))[0]
    assert_true(cancelled_invoice == "cancelled", "فاتورة البيع لم تُلغَ")
    assert_true(cancelled_delivery == ("cancelled", None), "إذن الصرف لم يُلغَ مع الفاتورة")
    assert_true(float(stock_after_sale_cancel) == 100.0, "المخزون لم يعد بعد إلغاء فاتورة البيع")
    assert_true(sales_order_status == "issued", "حالة أمر البيع لم تُحدّث بعد الإلغاء")

    purchase_order_resp = client.post(
        "/purchase-orders",
        data={
            "date": "2026-04-28",
            "supplier_id": str(supplier_id),
            "payment_terms": "اختبار",
            "delivery_date": "2026-04-28",
            "delivery_terms": "اختبار",
            "notes": "اختبار دورة المشتريات",
            "product_id[]": [str(product_id)],
            "quantity[]": ["10"],
            "unit_price[]": ["50"],
            "tax_rate[]": ["14"],
        },
        follow_redirects=False,
    )
    assert_true(purchase_order_resp.status_code in (302, 303), "فشل إنشاء أمر الشراء")
    purchase_order_id = fetchone(cur, "SELECT MAX(id) FROM purchase_orders")[0]
    purchase_order_line_id = fetchone(cur, "SELECT id FROM purchase_order_lines WHERE order_id=?", (purchase_order_id,))[0]

    receipt_resp = client.post(
        "/purchase-receipts",
        data={
            "date": "2026-04-28",
            "purchase_order_line_id": str(purchase_order_line_id),
            "received_quantity": "10",
            "notes": "اختبار إذن استلام",
        },
        follow_redirects=False,
    )
    assert_true(receipt_resp.status_code in (302, 303), "فشل إنشاء إذن الاستلام")
    receipt_id = fetchone(cur, "SELECT MAX(id) FROM purchase_receipts")[0]
    stock_after_receipt = fetchone(cur, "SELECT stock_quantity FROM products WHERE id=?", (product_id,))[0]
    assert_true(float(stock_after_receipt) == 110.0, "أثر المخزون بعد إذن الاستلام غير صحيح")

    purchase_invoice_resp = client.post(
        "/purchases/from-receipt",
        data={
            "date": "2026-04-28",
            "supplier_invoice_no": "SUP-INV-001",
            "supplier_invoice_date": "2026-04-28",
            "due_date": "2026-04-30",
            "payment_type": "credit",
            "notes": "اختبار فاتورة مشتريات من إذن استلام",
            "receipt_ids": [str(receipt_id)],
            f"vat_enabled_{receipt_id}": "1",
            f"vat_rate_{receipt_id}": "14",
        },
        follow_redirects=False,
    )
    assert_true(purchase_invoice_resp.status_code in (302, 303), "فشل إنشاء فاتورة المشتريات من إذن الاستلام")
    purchase_invoice_id = fetchone(cur, "SELECT MAX(id) FROM purchase_invoices")[0]
    purchase_invoice = fetchone(cur, "SELECT quantity,unit_price,total,status FROM purchase_invoices WHERE id=?", (purchase_invoice_id,))
    assert_true(tuple(map(float, purchase_invoice[:3])) == (10.0, 50.0, 500.0), "بيانات الكمية/السعر/الإجمالي في فاتورة المشتريات غير صحيحة")
    assert_true(purchase_invoice[3] == "posted", "حالة فاتورة المشتريات غير صحيحة")
    purchase_line = fetchone(cur, "SELECT quantity,unit_price,total FROM purchase_invoice_lines WHERE invoice_id=?", (purchase_invoice_id,))
    assert_true(tuple(map(float, purchase_line)) == (10.0, 50.0, 500.0), "بيانات بند فاتورة المشتريات غير صحيحة")
    receipt_row = fetchone(cur, "SELECT status,invoice_id FROM purchase_receipts WHERE id=?", (receipt_id,))
    assert_true(receipt_row == ("invoiced", purchase_invoice_id), "إذن الاستلام لم يتحول إلى مفوتر")

    purchase_print = client.get(f"/purchases/{purchase_invoice_id}/print")
    purchase_excel = client.get(f"/purchases/{purchase_invoice_id}/export")
    assert_true(purchase_print.status_code == 200, "طباعة فاتورة المشتريات فشلت")
    assert_true(purchase_excel.status_code == 200, "تصدير Excel لفاتورة المشتريات فشل")

    cancel_purchase_resp = client.post(
        f"/purchases/{purchase_invoice_id}/cancel",
        data={"reason": "اختبار إلغاء فاتورة مشتريات"},
        follow_redirects=False,
    )
    assert_true(cancel_purchase_resp.status_code in (302, 303), "فشل إلغاء فاتورة المشتريات")
    cancelled_purchase_invoice = fetchone(cur, "SELECT status FROM purchase_invoices WHERE id=?", (purchase_invoice_id,))[0]
    cancelled_receipt = fetchone(cur, "SELECT status,invoice_id FROM purchase_receipts WHERE id=?", (receipt_id,))
    stock_after_purchase_cancel = fetchone(cur, "SELECT stock_quantity FROM products WHERE id=?", (product_id,))[0]
    purchase_order_status = fetchone(cur, "SELECT status FROM purchase_orders WHERE id=?", (purchase_order_id,))[0]
    assert_true(cancelled_purchase_invoice == "cancelled", "فاتورة المشتريات لم تُلغَ")
    assert_true(cancelled_receipt == ("cancelled", None), "إذن الاستلام لم يُلغَ مع الفاتورة")
    assert_true(float(stock_after_purchase_cancel) == 100.0, "المخزون لم يعد بعد إلغاء فاتورة المشتريات")
    assert_true(purchase_order_status == "issued", "حالة أمر الشراء لم تُحدّث بعد الإلغاء")

    direct_sale_resp = client.post(
        "/sales",
        data={
            "date": "2026-04-28",
            "payment_type": "credit",
            "customer_id": str(customer_id),
            "due_date": "2026-04-30",
            "product_id": str(product_id),
            "quantity": "2",
            "unit_price": "100",
            "tax_rate": "14",
            "po_ref": "",
            "gr_ref": "",
            "notes": "فاتورة مباشرة لاختبار مردودات المبيعات",
        },
        follow_redirects=False,
    )
    assert_true(direct_sale_resp.status_code in (302, 303), "فشل إنشاء فاتورة بيع مباشرة")
    direct_sale_invoice_id = fetchone(cur, "SELECT MAX(id) FROM sales_invoices")[0]
    sales_return_resp = client.post(
        "/sales-returns",
        data={
            "date": "2026-04-28",
            "sales_invoice_id": str(direct_sale_invoice_id),
            "product_id[]": [str(product_id)],
            "quantity[]": ["1"],
            "po_ref": "",
            "gr_ref": "",
            "notes": "اختبار مردود بيع",
        },
        follow_redirects=False,
    )
    assert_true(sales_return_resp.status_code in (302, 303), "فشل تسجيل مردود المبيعات")
    sales_return_qty = fetchone(cur, "SELECT quantity FROM sales_returns WHERE sales_invoice_id=? ORDER BY id DESC LIMIT 1", (direct_sale_invoice_id,))[0]
    assert_true(float(sales_return_qty) == 1.0, "كمية مردود المبيعات غير صحيحة")

    direct_purchase_resp = client.post(
        "/purchases",
        data={
            "date": "2026-04-28",
            "supplier_invoice_no": "SUP-INV-002",
            "supplier_invoice_date": "2026-04-28",
            "due_date": "2026-04-30",
            "payment_type": "credit",
            "supplier_id": str(supplier_id),
            "product_id": str(product_id),
            "quantity": "3",
            "unit_price": "50",
            "tax_rate": "14",
            "notes": "فاتورة مباشرة لاختبار مردودات المشتريات",
        },
        follow_redirects=False,
    )
    assert_true(direct_purchase_resp.status_code in (302, 303), "فشل إنشاء فاتورة مشتريات مباشرة")
    direct_purchase_invoice_id = fetchone(cur, "SELECT MAX(id) FROM purchase_invoices")[0]
    purchase_return_resp = client.post(
        "/purchase-returns",
        data={
            "date": "2026-04-28",
            "purchase_invoice_id": str(direct_purchase_invoice_id),
            "product_id[]": [str(product_id)],
            "quantity[]": ["1"],
            "po_ref": "",
            "gr_ref": "",
            "notes": "اختبار مردود مشتريات",
        },
        follow_redirects=False,
    )
    assert_true(purchase_return_resp.status_code in (302, 303), "فشل تسجيل مردود المشتريات")
    purchase_return_qty = fetchone(cur, "SELECT quantity FROM purchase_returns WHERE purchase_invoice_id=? ORDER BY id DESC LIMIT 1", (direct_purchase_invoice_id,))[0]
    assert_true(float(purchase_return_qty) == 1.0, "كمية مردود المشتريات غير صحيحة")

    category_page = client.get("/product-categories")
    assert_true(category_page.status_code == 200, "صفحة تصنيفات الأصناف لا تعمل")
    create_parent = client.post("/product-categories", data={"name": "تصنيف اختبار", "parent_id": "", "action": "save"}, follow_redirects=False)
    assert_true(create_parent.status_code in (302, 303), "فشل إنشاء تصنيف رئيسي")
    parent_id = fetchone(cur, "SELECT MAX(id) FROM product_categories")[0]
    create_child = client.post("/product-categories", data={"name": "تصنيف فرعي اختبار", "parent_id": str(parent_id), "action": "save"}, follow_redirects=False)
    assert_true(create_child.status_code in (302, 303), "فشل إنشاء تصنيف فرعي")

    smoke_paths = [
        "/dashboard",
        "/products",
        "/inventory",
        "/reports/inventory",
        "/e-invoices",
    ]
    smoke_results = {}
    for path in smoke_paths:
        response = client.get(path)
        smoke_results[path] = response.status_code
        assert_true(response.status_code == 200, f"فشل فتح الصفحة {path}")

    prepare_einvoice = client.post("/e-invoices/prepare-sales", follow_redirects=False)
    assert_true(prepare_einvoice.status_code in (302, 303), "فشل تجهيز الفواتير الإلكترونية")

    conn.close()
    appmod.DB_PATH = old_db_path
    appmod.MODULE_DEPS["DB_PATH"] = old_module_db_path

    result = {
        "temp_db": str(temp_db),
        "sales_invoice_id": sales_invoice_id,
        "purchase_invoice_id": purchase_invoice_id,
        "direct_sale_invoice_id": direct_sale_invoice_id,
        "direct_purchase_invoice_id": direct_purchase_invoice_id,
        "smoke_results": smoke_results,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
