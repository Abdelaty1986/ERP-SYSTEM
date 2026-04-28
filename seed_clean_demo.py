import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"
BACKUP_DIR = BASE_DIR / "backups"
REPORT_PATH = BASE_DIR / "DEMO_READY_REPORT.md"


def create_backup():
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"before_seed_demo_{stamp}.db"
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def scalar(cur, query, params=()):
    cur.execute(query, params)
    row = cur.fetchone()
    return row[0] if row else None


def rebuild_ledger(cur):
    cur.execute("DELETE FROM ledger")
    cur.execute(
        """
        SELECT id,date,description,debit_account_id,credit_account_id,amount
        FROM journal
        WHERE status='posted'
        ORDER BY id
        """
    )
    for journal_id, date_value, description, debit_account_id, credit_account_id, amount in cur.fetchall():
        cur.execute(
            "INSERT INTO ledger(account_id,date,description,debit,credit,journal_id) VALUES (?,?,?,?,?,?)",
            (debit_account_id, date_value, description, amount, 0, journal_id),
        )
        cur.execute(
            "INSERT INTO ledger(account_id,date,description,debit,credit,journal_id) VALUES (?,?,?,?,?,?)",
            (credit_account_id, date_value, description, 0, amount, journal_id),
        )


def account_id(cur, code):
    value = scalar(cur, "SELECT id FROM accounts WHERE code=?", (code,))
    if not value:
        raise RuntimeError(f"Missing account code: {code}")
    return value


def create_journal(cur, date_value, description, debit_code, credit_code, amount, source_type="manual", source_id=None):
    debit_account_id = account_id(cur, debit_code)
    credit_account_id = account_id(cur, credit_code)
    cur.execute(
        """
        INSERT INTO journal(date,description,debit_account_id,credit_account_id,amount,status,source_type,source_id)
        VALUES (?,?,?,?,?,'posted',?,?)
        """,
        (date_value, description, debit_account_id, credit_account_id, amount, source_type, source_id),
    )
    return cur.lastrowid


def ensure_company_settings(cur):
    cur.execute(
        """
        INSERT INTO company_settings(id,company_name,tax_number,commercial_register,address,phone,email,default_tax_rate,invoice_footer)
        VALUES (1,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            company_name=excluded.company_name,
            tax_number=excluded.tax_number,
            commercial_register=excluded.commercial_register,
            address=excluded.address,
            phone=excluded.phone,
            email=excluded.email,
            default_tax_rate=excluded.default_tax_rate,
            invoice_footer=excluded.invoice_footer
        """,
        (
            "شركة جولدن ديمو للصناعات",
            "312-456-789",
            "س.ت 778899 القاهرة",
            "المنطقة الصناعية - العبور - القاهرة",
            "02-24567890",
            "demo@golden-erp.local",
            14,
            "نسخة عرض توضيحية مترابطة للنظام المحاسبي والتشغيلي.",
        ),
    )


def clear_non_account_data(cur):
    tables = [
        "e_invoice_documents",
        "invoice_allocations",
        "financial_sales_invoice_lines",
        "sales_invoice_lines",
        "purchase_invoice_lines",
        "payroll_lines",
        "sales_credit_notes",
        "supplier_debit_notes",
        "customer_adjustments",
        "sales_returns",
        "purchase_returns",
        "sales_delivery_notes",
        "purchase_receipts",
        "receipt_vouchers",
        "payment_vouchers",
        "financial_sales_invoices",
        "sales_invoices",
        "purchase_invoices",
        "sales_order_lines",
        "purchase_order_lines",
        "sales_orders",
        "purchase_orders",
        "inventory_movements",
        "payroll_runs",
        "employees",
        "products",
        "customers",
        "suppliers",
        "cost_centers",
        "journal",
        "ledger",
        "audit_log",
        "year_end_closings",
        "document_sequences",
        "posting_control",
        "fiscal_periods",
    ]
    for table_name in tables:
        cur.execute(f"DELETE FROM {table_name}")
    cur.execute(
        "DELETE FROM sqlite_sequence WHERE name IN ({})".format(",".join(["?"] * len(tables))),
        tables,
    )


def seed_reference_data(cur):
    cur.execute(
        """
        INSERT INTO fiscal_periods(name,start_date,end_date,status,notes)
        VALUES (?,?,?,?,?)
        """,
        ("السنة المالية 2026", "2026-01-01", "2026-12-31", "open", "فترة عرض توضيحي"),
    )

    for group_key, group_name in [
        ("manual_journal", "القيود اليومية"),
        ("sales", "فواتير البيع"),
        ("purchases", "فواتير الموردين"),
        ("receipts", "سندات القبض"),
        ("payments", "سندات الصرف"),
    ]:
        cur.execute(
            """
            INSERT INTO posting_control(group_key,group_name,is_posted,posted_at,posted_by)
            VALUES (?,?,1,CURRENT_TIMESTAMP,'system')
            """,
            (group_key, group_name),
        )

    for doc_type, prefix, next_number in [
        ("sales", "SI", 2),
        ("purchases", "PI", 2),
        ("sales_delivery_notes", "DN", 2),
        ("purchase_receipts", "GRN", 2),
        ("sales_credit_notes", "SCN", 1),
        ("supplier_debit_notes", "SDN", 1),
        ("customer_adjustments", "ADJ", 1),
        ("financial_sales", "FSI", 1),
    ]:
        cur.execute(
            "INSERT INTO document_sequences(doc_type,prefix,next_number) VALUES (?,?,?)",
            (doc_type, prefix, next_number),
        )

    cur.executemany(
        "INSERT INTO cost_centers(code,name,center_type,status,notes) VALUES (?,?,?,?,?)",
        [
            ("PRD-01", "خط الإنتاج الرئيسي", "إنتاج", "active", "مركز تكلفة ديمو"),
            ("SAL-01", "إدارة المبيعات", "بيع", "active", "مركز تكلفة ديمو"),
            ("ADM-01", "الإدارة العامة", "إدارة", "active", "مركز تكلفة ديمو"),
        ],
    )

    cur.executemany(
        """
        INSERT INTO customers(name,phone,address,tax_registration_number,tax_card_number,commercial_register,contact_person,email,withholding_status)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        [
            ("عميل جولدن ديمو - خاضع", "01000000010", "القاهرة", "TRN-C-001", "TC-C-001", "", "أحمد سالم", "customer.subject@demo.local", "subject"),
            ("عميل جولدن ديمو - عادي", "01000000011", "الجيزة", "TRN-C-002", "TC-C-002", "", "منى شريف", "customer.normal@demo.local", "non_subject"),
        ],
    )

    cur.executemany(
        """
        INSERT INTO suppliers(name,phone,address,tax_registration_number,tax_card_number,commercial_register,contact_person,email,withholding_status)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        [
            ("مورد جولدن ديمو - خاضع", "01000000020", "العاشر من رمضان", "TRN-S-001", "TC-S-001", "", "محمد فوزي", "supplier.taxable@demo.local", "taxable"),
            ("مورد جولدن ديمو - معفي", "01000000021", "6 أكتوبر", "TRN-S-002", "TC-S-002", "", "سارة علي", "supplier.exempt@demo.local", "exempt"),
        ],
    )

    cur.executemany(
        "INSERT INTO products(code,name,unit,purchase_price,sale_price,stock_quantity) VALUES (?,?,?,?,?,?)",
        [
            ("GD-RAW-001", "خام ألواح معدنية", "قطعة", 50, 0, 200),
            ("GD-FG-001", "منتج نهائي قياسي", "قطعة", 55, 90, 120),
        ],
    )


def seed_demo_transactions(cur):
    customer_subject_id = scalar(cur, "SELECT id FROM customers WHERE name='عميل جولدن ديمو - خاضع'")
    customer_normal_id = scalar(cur, "SELECT id FROM customers WHERE name='عميل جولدن ديمو - عادي'")
    supplier_taxable_id = scalar(cur, "SELECT id FROM suppliers WHERE name='مورد جولدن ديمو - خاضع'")
    supplier_exempt_id = scalar(cur, "SELECT id FROM suppliers WHERE name='مورد جولدن ديمو - معفي'")
    raw_product_id = scalar(cur, "SELECT id FROM products WHERE code='GD-RAW-001'")
    finished_product_id = scalar(cur, "SELECT id FROM products WHERE code='GD-FG-001'")

    # Opening balances
    create_journal(cur, "2026-01-01", "رصيد افتتاحي الخزينة", "1100", "3100", 150000, "opening")
    create_journal(cur, "2026-01-01", "رصيد افتتاحي البنك", "1200", "3100", 250000, "opening")
    create_journal(cur, "2026-01-01", "رصيد افتتاحي المخزون", "1400", "3100", 16600, "opening")
    cur.executemany(
        """
        INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes)
        VALUES (?,?,?,?,?,?,?)
        """,
        [
            ("2026-01-01", raw_product_id, "opening", 200, "opening", None, "رصيد افتتاحي خام"),
            ("2026-01-01", finished_product_id, "opening", 120, "opening", None, "رصيد افتتاحي منتج نهائي"),
        ],
    )

    # Purchase order and receipt
    cur.execute(
        """
        INSERT INTO purchase_orders(date,supplier_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total,payment_terms,delivery_date,delivery_terms,notes,status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("2026-04-10", supplier_taxable_id, raw_product_id, 120, 50, 6000, 14, 840, 6840, "أجل 30 يوم", "2026-04-12", "استلام مخزني", "أمر شراء خامات", "issued"),
    )
    purchase_order_id = cur.lastrowid
    cur.execute(
        """
        INSERT INTO purchase_order_lines(order_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (purchase_order_id, raw_product_id, 120, 50, 6000, 14, 840, 6840),
    )
    purchase_order_line_id = cur.lastrowid

    purchase_receipt_journal_id = create_journal(cur, "2026-04-12", "إذن إضافة GRN-000001", "1400", "2150", 6000, "purchase_receipt")
    cur.execute(
        """
        INSERT INTO purchase_receipts(receipt_no,date,purchase_order_id,purchase_order_line_id,supplier_id,product_id,ordered_quantity,received_quantity,unit_price,total,tax_rate,tax_amount,grand_total,journal_id,status,notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("GRN-000001", "2026-04-12", purchase_order_id, purchase_order_line_id, supplier_taxable_id, raw_product_id, 120, 120, 50, 6000, 14, 840, 6840, purchase_receipt_journal_id, "received", "استلام خامات من المورد"),
    )
    purchase_receipt_id = cur.lastrowid
    cur.execute("UPDATE products SET stock_quantity=stock_quantity+120, purchase_price=50 WHERE id=?", (raw_product_id,))
    cur.execute(
        """
        INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes)
        VALUES (?,?,?,?,?,?,?)
        """,
        ("2026-04-12", raw_product_id, "in", 120, "purchase_receipt", purchase_receipt_id, "إذن إضافة GRN-000001"),
    )

    purchase_invoice_journal_id = create_journal(cur, "2026-04-13", "فاتورة مورد PI-000001", "2150", "2100", 6000, "purchase_invoice")
    purchase_tax_journal_id = create_journal(cur, "2026-04-13", "ضريبة فاتورة مورد PI-000001", "1500", "2100", 840, "purchase_invoice")
    purchase_withholding_journal_id = create_journal(cur, "2026-04-13", "خصم وإضافة مورد PI-000001", "2100", "2230", 68.4, "purchase_invoice")
    cur.execute(
        """
        INSERT INTO purchase_invoices(
            date,doc_no,supplier_invoice_no,supplier_invoice_date,due_date,supplier_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,withholding_rate,withholding_amount,grand_total,payment_type,journal_id,tax_journal_id,withholding_journal_id,notes,status,purchase_order_id,purchase_receipt_id
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("2026-04-13", "PI-000001", "SUP-INV-001", "2026-04-13", "2026-05-13", supplier_taxable_id, raw_product_id, 120, 50, 6000, 14, 840, 1, 68.4, 6840, "credit", purchase_invoice_journal_id, purchase_tax_journal_id, purchase_withholding_journal_id, "فاتورة مورد من إذن إضافة", "posted", purchase_order_id, purchase_receipt_id),
    )
    purchase_invoice_id = cur.lastrowid
    cur.execute(
        "INSERT INTO purchase_invoice_lines(invoice_id,product_id,quantity,unit_price,total) VALUES (?,?,?,?,?)",
        (purchase_invoice_id, raw_product_id, 120, 50, 6000),
    )
    cur.execute("UPDATE purchase_receipts SET invoice_id=?, status='invoiced' WHERE id=?", (purchase_invoice_id, purchase_receipt_id))

    # Second direct supplier invoice for exempt supplier
    exempt_purchase_journal_id = create_journal(cur, "2026-04-15", "فاتورة مورد مباشرة PI-000002", "1400", "2100", 2400, "purchase_invoice")
    exempt_purchase_tax_journal_id = create_journal(cur, "2026-04-15", "ضريبة فاتورة مورد مباشرة PI-000002", "1500", "2100", 336, "purchase_invoice")
    cur.execute(
        """
        INSERT INTO purchase_invoices(
            date,doc_no,supplier_invoice_no,supplier_invoice_date,due_date,supplier_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,withholding_rate,withholding_amount,grand_total,payment_type,journal_id,tax_journal_id,withholding_journal_id,notes,status
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("2026-04-15", "PI-000002", "SUP-INV-002", "2026-04-15", "2026-05-15", supplier_exempt_id, raw_product_id, 48, 50, 2400, 14, 336, 0, 0, 2736, "credit", exempt_purchase_journal_id, exempt_purchase_tax_journal_id, None, "فاتورة مورد مباشرة بدون إذن", "posted"),
    )
    direct_purchase_invoice_id = cur.lastrowid
    cur.execute(
        "INSERT INTO purchase_invoice_lines(invoice_id,product_id,quantity,unit_price,total) VALUES (?,?,?,?,?)",
        (direct_purchase_invoice_id, raw_product_id, 48, 50, 2400),
    )
    cur.execute("UPDATE products SET stock_quantity=stock_quantity+48 WHERE id=?", (raw_product_id,))
    cur.execute(
        """
        INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes)
        VALUES (?,?,?,?,?,?,?)
        """,
        ("2026-04-15", raw_product_id, "in", 48, "purchase", direct_purchase_invoice_id, "فاتورة مورد مباشرة"),
    )

    # Sales order and delivery
    cur.execute(
        """
        INSERT INTO sales_orders(date,customer_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total,payment_terms,delivery_date,notes,status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("2026-04-16", customer_subject_id, finished_product_id, 60, 90, 5400, 14, 756, 6156, "أجل 15 يوم", "2026-04-17", "أمر بيع منتج نهائي", "issued"),
    )
    sales_order_id = cur.lastrowid
    cur.execute(
        """
        INSERT INTO sales_order_lines(order_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (sales_order_id, finished_product_id, 60, 90, 5400, 14, 756, 6156),
    )
    sales_order_line_id = cur.lastrowid

    sales_delivery_cogs_journal_id = create_journal(cur, "2026-04-17", "إذن صرف DN-000001", "6100", "1400", 3300, "sales_delivery")
    cur.execute(
        """
        INSERT INTO sales_delivery_notes(delivery_no,date,sales_order_id,sales_order_line_id,customer_id,product_id,ordered_quantity,delivered_quantity,unit_price,total,cost_total,tax_rate,tax_amount,grand_total,cogs_journal_id,status,notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("DN-000001", "2026-04-17", sales_order_id, sales_order_line_id, customer_subject_id, finished_product_id, 60, 60, 90, 5400, 3300, 14, 756, 6156, sales_delivery_cogs_journal_id, "delivered", "صرف من المخزن لأمر البيع"),
    )
    sales_delivery_id = cur.lastrowid
    cur.execute("UPDATE products SET stock_quantity=stock_quantity-60 WHERE id=?", (finished_product_id,))
    cur.execute(
        """
        INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes)
        VALUES (?,?,?,?,?,?,?)
        """,
        ("2026-04-17", finished_product_id, "out", -60, "sales_delivery", sales_delivery_id, "إذن صرف DN-000001"),
    )

    sales_invoice_journal_id = create_journal(cur, "2026-04-18", "فاتورة بيع SI-000001", "1300", "4100", 5400, "sales_invoice")
    sales_tax_journal_id = create_journal(cur, "2026-04-18", "ضريبة فاتورة بيع SI-000001", "1300", "2200", 756, "sales_invoice")
    sales_withholding_journal_id = create_journal(cur, "2026-04-18", "خصم وإضافة عميل SI-000001", "1510", "1300", 61.56, "sales_invoice")
    cur.execute(
        """
        INSERT INTO sales_invoices(
            date,due_date,doc_no,customer_id,product_id,quantity,unit_price,total,cost_total,tax_rate,tax_amount,withholding_rate,withholding_amount,grand_total,payment_type,journal_id,tax_journal_id,withholding_journal_id,cogs_journal_id,status,sales_order_id,sales_delivery_id,po_ref,gr_ref,notes
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("2026-04-18", "2026-05-03", "SI-000001", customer_subject_id, finished_product_id, 60, 90, 5400, 3300, 14, 756, 1, 61.56, 6156, "credit", sales_invoice_journal_id, sales_tax_journal_id, sales_withholding_journal_id, None, "posted", sales_order_id, sales_delivery_id, "PO-DEM-001", "DN-000001", "فاتورة بيع من إذن صرف"),
    )
    sales_invoice_id = cur.lastrowid
    cur.execute(
        "INSERT INTO sales_invoice_lines(invoice_id,product_id,quantity,unit_price,total,cost_total) VALUES (?,?,?,?,?,?)",
        (sales_invoice_id, finished_product_id, 60, 90, 5400, 3300),
    )
    cur.execute("UPDATE sales_delivery_notes SET invoice_id=?, status='invoiced' WHERE id=?", (sales_invoice_id, sales_delivery_id))

    # Direct financial sales invoice to normal customer
    financial_sales_journal_id = create_journal(cur, "2026-04-19", "فاتورة بيع مالية FSI-000001", "1100", "4500", 2000, "financial_sales")
    financial_sales_tax_journal_id = create_journal(cur, "2026-04-19", "ضريبة فاتورة بيع مالية FSI-000001", "1100", "2200", 280, "financial_sales")
    cur.execute(
        """
        INSERT INTO financial_sales_invoices(
            date,due_date,doc_no,customer_id,description,amount,tax_rate,tax_amount,withholding_rate,withholding_amount,grand_total,payment_type,revenue_account_id,journal_id,tax_journal_id,withholding_journal_id,status,po_ref,gr_ref,notes
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "2026-04-19",
            "2026-04-19",
            "FSI-000001",
            customer_normal_id,
            "فاتورة خدمات مالية",
            2000,
            14,
            280,
            0,
            0,
            2280,
            "cash",
            account_id(cur, "4500"),
            financial_sales_journal_id,
            financial_sales_tax_journal_id,
            None,
            "posted",
            "",
            "",
            "فاتورة مالية مباشرة",
        ),
    )
    financial_sales_invoice_id = cur.lastrowid
    cur.execute(
        "INSERT INTO financial_sales_invoice_lines(invoice_id,description,amount) VALUES (?,?,?)",
        (financial_sales_invoice_id, "خدمات تركيب وإعداد", 2000),
    )

    # Treasury
    receipt_journal_id = create_journal(cur, "2026-04-20", "سند قبض من العميل", "1100", "1300", 3000, "receipt")
    cur.execute(
        "INSERT INTO receipt_vouchers(date,customer_id,amount,notes,journal_id,status) VALUES (?,?,?,?,?,'posted')",
        ("2026-04-20", customer_subject_id, 3000, "تحصيل جزئي من العميل", receipt_journal_id),
    )

    payment_journal_id = create_journal(cur, "2026-04-20", "سند صرف للمورد", "2100", "1100", 2000, "payment")
    cur.execute(
        "INSERT INTO payment_vouchers(date,supplier_id,amount,notes,journal_id,status) VALUES (?,?,?,?,?,'posted')",
        ("2026-04-20", supplier_taxable_id, 2000, "سداد جزئي للمورد", payment_journal_id),
    )

    # Manual journal for demo accounting review
    create_journal(cur, "2026-04-21", "قيد مصروفات إدارية", "5100", "1100", 1500, "manual")

    rebuild_ledger(cur)


def write_report(cur, backup_path):
    trial_totals = cur.execute("SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) FROM ledger").fetchone()
    report = f"""# Demo Ready Report

- Backup: `{backup_path.name}`
- Accounts kept: `{scalar(cur, "SELECT COUNT(*) FROM accounts")}`
- Customers: `{scalar(cur, "SELECT COUNT(*) FROM customers")}`
- Suppliers: `{scalar(cur, "SELECT COUNT(*) FROM suppliers")}`
- Products: `{scalar(cur, "SELECT COUNT(*) FROM products")}`
- Journal entries: `{scalar(cur, "SELECT COUNT(*) FROM journal")}`
- Ledger lines: `{scalar(cur, "SELECT COUNT(*) FROM ledger")}`

## Scenario

1. Opening balances for cash, bank, and inventory.
2. Purchase order + goods receipt + supplier invoice for a taxable supplier.
3. Direct supplier invoice for an exempt supplier.
4. Sales order + delivery note + customer invoice for a taxable customer.
5. Direct financial sales invoice for a normal customer.
6. Partial receipt from customer and partial payment to supplier.
7. One manual administrative expense journal.

## Accounting Check

- Trial debit: `{trial_totals[0]:.2f}`
- Trial credit: `{trial_totals[1]:.2f}`
- Balanced: `{"yes" if round(trial_totals[0], 2) == round(trial_totals[1], 2) else "no"}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main():
    backup_path = create_backup()
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = OFF")
    cur.execute("PRAGMA busy_timeout = 30000")
    ensure_company_settings(cur)
    clear_non_account_data(cur)
    seed_reference_data(cur)
    seed_demo_transactions(cur)
    write_report(cur, backup_path)
    cur.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    conn.close()
    print(f"Backup created: {backup_path}")
    print("Clean demo data seeded successfully.")
    print(f"Report written: {REPORT_PATH}")


if __name__ == "__main__":
    main()
