import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB = BASE_DIR / "database.db"
BACKUP_DIR = BASE_DIR / "backups"


ACCOUNTS = [
    ("1000", "الأصول", "أصول"),
    ("1100", "الخزينة", "أصول"),
    ("1110", "خزينة المصنع", "أصول"),
    ("1120", "خزينة الإدارة", "أصول"),
    ("1200", "البنوك", "أصول"),
    ("1210", "بنك مصر - حساب جاري", "أصول"),
    ("1220", "ودائع بنكية قصيرة الأجل", "أصول"),
    ("1300", "العملاء", "أصول"),
    ("1310", "عملاء محليون", "أصول"),
    ("1320", "أوراق قبض", "أصول"),
    ("1330", "مخصص ديون مشكوك فيها", "أصول"),
    ("1400", "المخزون", "أصول"),
    ("1410", "مخزون خامات", "أصول"),
    ("1420", "إنتاج تحت التشغيل", "أصول"),
    ("1430", "مخزون إنتاج تام", "أصول"),
    ("1440", "مخزون قطع غيار ومستلزمات", "أصول"),
    ("1450", "بضاعة بالطريق", "أصول"),
    ("1500", "ضريبة قيمة مضافة - مدخلات", "أصول"),
    ("1600", "مصروفات مقدمة", "أصول"),
    ("1700", "عهد وسلف عاملين", "أصول"),
    ("1800", "الأصول الثابتة", "أصول"),
    ("1810", "أراضي", "أصول"),
    ("1820", "مبان وإنشاءات", "أصول"),
    ("1830", "آلات ومعدات إنتاج", "أصول"),
    ("1840", "سيارات ووسائل نقل", "أصول"),
    ("1850", "أثاث وأجهزة مكتبية", "أصول"),
    ("1860", "مجمع إهلاك الأصول الثابتة", "أصول"),
    ("1900", "حساب افتتاحي تجميعي", "أصول"),
    ("2000", "الخصوم", "خصوم"),
    ("2100", "الموردون", "خصوم"),
    ("2110", "موردو خامات", "خصوم"),
    ("2120", "موردو خدمات", "خصوم"),
    ("2130", "أوراق دفع", "خصوم"),
    ("2150", "استلامات مشتريات غير مفوترة GR/IR", "خصوم"),
    ("2200", "ضريبة قيمة مضافة - مخرجات", "خصوم"),
    ("2210", "ضرائب مستحقة", "خصوم"),
    ("2220", "تأمينات اجتماعية مستحقة", "خصوم"),
    ("2300", "مصروفات مستحقة", "خصوم"),
    ("2310", "أجور مستحقة", "خصوم"),
    ("2320", "كهرباء ومرافق مستحقة", "خصوم"),
    ("2330", "استقطاعات عاملين مستحقة", "خصوم"),
    ("2340", "ضريبة كسب عمل مستحقة", "خصوم"),
    ("2400", "قروض قصيرة الأجل", "خصوم"),
    ("2500", "قروض طويلة الأجل", "خصوم"),
    ("3000", "حقوق الملكية", "حقوق ملكية"),
    ("3100", "رأس المال", "حقوق ملكية"),
    ("3200", "جاري الشركاء", "حقوق ملكية"),
    ("3300", "الأرباح المحتجزة", "حقوق ملكية"),
    ("3400", "صافي ربح أو خسارة العام", "حقوق ملكية"),
    ("4000", "الإيرادات", "إيرادات"),
    ("4100", "إيرادات المبيعات", "إيرادات"),
    ("4110", "مبيعات محلية", "إيرادات"),
    ("4120", "مبيعات تصدير", "إيرادات"),
    ("4200", "مردودات ومسموحات المبيعات", "إيرادات"),
    ("4300", "خصم مسموح به", "إيرادات"),
    ("4400", "إيرادات أخرى", "إيرادات"),
    ("4500", "إيرادات خدمات وفواتير مالية", "إيرادات"),
    ("5000", "مصروفات التشغيل", "مصروفات"),
    ("5100", "مصروفات إدارية وعمومية", "مصروفات"),
    ("5110", "مرتبات الإدارة", "مصروفات"),
    ("5120", "إيجار إداري", "مصروفات"),
    ("5130", "اتصالات وإنترنت", "مصروفات"),
    ("5140", "مهمات مكتبية", "مصروفات"),
    ("5150", "مصروفات قانونية ومهنية", "مصروفات"),
    ("5160", "مصروفات علاج وتدريب عاملين", "مصروفات"),
    ("5170", "حصة الشركة في التأمينات الاجتماعية", "مصروفات"),
    ("5200", "مصروفات بيع وتسويق", "مصروفات"),
    ("5210", "عمولات مبيعات", "مصروفات"),
    ("5220", "دعاية وإعلان", "مصروفات"),
    ("5230", "نقل وتوزيع", "مصروفات"),
    ("5300", "مصروفات تمويلية", "مصروفات"),
    ("5310", "فوائد بنكية", "مصروفات"),
    ("5320", "مصروفات بنكية", "مصروفات"),
    ("6000", "تكاليف الإنتاج", "مصروفات"),
    ("6100", "تكلفة البضاعة المباعة", "مصروفات"),
    ("6200", "خامات مباشرة", "مصروفات"),
    ("6300", "أجور مباشرة", "مصروفات"),
    ("6400", "تكاليف صناعية غير مباشرة", "مصروفات"),
    ("6410", "كهرباء المصنع", "مصروفات"),
    ("6420", "صيانة آلات", "مصروفات"),
    ("6430", "إهلاك آلات ومعدات", "مصروفات"),
    ("6440", "مستلزمات تشغيل", "مصروفات"),
    ("6450", "رقابة جودة", "مصروفات"),
]


CUSTOMERS = [
    ("CUST-001", "شركة النور للتوزيع", "01010000001", "مدينة نصر - القاهرة", "498-223-110", "TAX-C-1001", "CR-1101", "أحمد فتحي", "finance@elnour.example"),
    ("CUST-002", "المصرية للتوريدات الهندسية", "01010000002", "المنطقة الصناعية - العبور", "498-223-120", "TAX-C-1002", "CR-1102", "منى عادل", "ap@egy-eng.example"),
    ("CUST-003", "دلتا للمقاولات والصيانة", "01010000003", "طنطا - الغربية", "498-223-130", "TAX-C-1003", "CR-1103", "سامح نبيل", "accounts@delta.example"),
    ("CUST-004", "الفجر للتجارة", "01010000004", "الإسكندرية", "498-223-140", "TAX-C-1004", "CR-1104", "هالة سمير", "finance@fagr.example"),
]


SUPPLIERS = [
    ("SUP-001", "دلتا ستيل للخامات", "01020000001", "العاشر من رمضان", "598-112-210", "TAX-S-2001", "CR-2101", "كريم محمود", "ar@deltasteel.example"),
    ("SUP-002", "المتحدة للكيماويات", "01020000002", "برج العرب", "598-112-220", "TAX-S-2002", "CR-2102", "نجلاء يوسف", "billing@chem.example"),
    ("SUP-003", "باك لاين للتغليف", "01020000003", "6 أكتوبر", "598-112-230", "TAX-S-2003", "CR-2103", "أشرف علي", "accounts@packline.example"),
    ("SUP-004", "تكنو سيرفيس للصيانة", "01020000004", "القاهرة الجديدة", "598-112-240", "TAX-S-2004", "CR-2104", "محمود زكي", "finance@techservice.example"),
]


PRODUCTS = [
    ("RM-STL-001", "صاج مجلفن خام 1.2 مم", "كجم", 44.0, 0.0, 3500.0),
    ("RM-PLA-001", "حبيبات بلاستيك HDPE", "كجم", 29.0, 0.0, 2800.0),
    ("RM-PNT-001", "دهان صناعي مقاوم", "كجم", 92.0, 0.0, 750.0),
    ("PKG-BOX-001", "كرتون تعبئة مطبوع", "قطعة", 3.5, 0.0, 7500.0),
    ("FG-BOX-001", "صندوق كهرباء معدني مقاس M", "قطعة", 420.0, 950.0, 1000.0),
    ("FG-PNL-001", "لوحة توزيع صناعية 12 خط", "قطعة", 520.0, 1450.0, 280.0),
    ("SP-BLT-001", "مسامير وقطع غيار تشغيل", "وحدة", 1.5, 0.0, 6000.0),
]


def backup_database():
    BACKUP_DIR.mkdir(exist_ok=True)
    if DB.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"database_before_industrial_demo_{stamp}.db"
        shutil.copy2(DB, backup_path)
        return backup_path
    return None


def main():
    backup_path = backup_database()
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = OFF")

    clear_tables = [
        "ledger",
        "invoice_allocations",
        "financial_sales_invoice_lines",
        "sales_invoice_lines",
        "purchase_invoice_lines",
        "payroll_lines",
        "payroll_runs",
        "e_invoice_documents",
        "year_end_closings",
        "sales_returns",
        "purchase_returns",
        "sales_delivery_notes",
        "purchase_receipts",
        "sales_order_lines",
        "purchase_order_lines",
        "sales_invoices",
        "purchase_invoices",
        "financial_sales_invoices",
        "sales_orders",
        "purchase_orders",
        "inventory_movements",
        "receipt_vouchers",
        "payment_vouchers",
        "journal",
        "audit_log",
        "posting_control",
        "fiscal_periods",
        "document_sequences",
        "employees",
        "products",
        "customers",
        "suppliers",
        "cost_centers",
        "accounts",
    ]
    for table in clear_tables:
        cur.execute(f"DELETE FROM {table}")
    cur.execute(
        "DELETE FROM sqlite_sequence WHERE name IN ({})".format(
            ",".join(["?"] * len(clear_tables))
        ),
        clear_tables,
    )

    cur.execute(
        """
        UPDATE company_settings
        SET company_name=?,tax_number=?,commercial_register=?,address=?,phone=?,email=?,default_tax_rate=?,invoice_footer=?
        WHERE id=1
        """,
        (
            "شركة الأمل للصناعات الهندسية ش.م.م",
            "498-776-320",
            "س.ت 458921 صناعي القاهرة",
            "المنطقة الصناعية - العبور - جمهورية مصر العربية",
            "02-44890011",
            "finance@alamal-industries.example",
            14,
            "شكرا لتعاملكم مع شركة الأمل للصناعات الهندسية",
        ),
    )
    if cur.rowcount == 0:
        cur.execute(
            """
            INSERT INTO company_settings(id,company_name,tax_number,commercial_register,address,phone,email,default_tax_rate,invoice_footer)
            VALUES (1,?,?,?,?,?,?,?,?)
            """,
            (
                "شركة الأمل للصناعات الهندسية ش.م.م",
                "498-776-320",
                "س.ت 458921 صناعي القاهرة",
                "المنطقة الصناعية - العبور - جمهورية مصر العربية",
                "02-44890011",
                "finance@alamal-industries.example",
                14,
                "شكرا لتعاملكم مع شركة الأمل للصناعات الهندسية",
            ),
        )

    cur.executemany("INSERT INTO accounts(code,name,type) VALUES (?,?,?)", ACCOUNTS)

    def acc(code):
        cur.execute("SELECT id FROM accounts WHERE code=?", (code,))
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"Missing account {code}")
        return row[0]

    def journal(date_value, desc, debit_code, credit_code, amount, source_type="manual", source_id=None, cost_center_id=None):
        cur.execute(
            """
            INSERT INTO journal(date,description,debit_account_id,credit_account_id,amount,status,source_type,source_id,cost_center_id)
            VALUES (?,?,?,?,?,'posted',?,?,?)
            """,
            (date_value, desc, acc(debit_code), acc(credit_code), amount, source_type, source_id, cost_center_id),
        )
        return cur.lastrowid

    cost_centers = [
        ("PRD-01", "خط إنتاج الصناديق المعدنية", "إنتاج", "active", "مركز تكلفة مباشر"),
        ("PRD-02", "خط تجميع لوحات التوزيع", "إنتاج", "active", "مركز تكلفة مباشر"),
        ("ADM-01", "الإدارة العامة", "إدارة", "active", ""),
        ("SAL-01", "المبيعات والتوزيع", "بيع", "active", ""),
    ]
    cur.executemany("INSERT INTO cost_centers(code,name,center_type,status,notes) VALUES (?,?,?,?,?)", cost_centers)
    cur.execute("SELECT id,code FROM cost_centers")
    cc = {code: cid for cid, code in cur.fetchall()}

    cur.executemany(
        """
        INSERT INTO customers(name,phone,address,tax_registration_number,tax_card_number,commercial_register,contact_person,email)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        [row[1:] for row in CUSTOMERS],
    )
    cur.executemany(
        """
        INSERT INTO suppliers(name,phone,address,tax_registration_number,tax_card_number,commercial_register,contact_person,email)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        [row[1:] for row in SUPPLIERS],
    )
    cur.executemany(
        "INSERT INTO products(code,name,unit,purchase_price,sale_price,stock_quantity) VALUES (?,?,?,?,?,?)",
        PRODUCTS,
    )

    def id_by_code(table, code):
        cur.execute(f"SELECT id FROM {table} WHERE code=?", (code,))
        return cur.fetchone()[0]

    customers = {code: idx + 1 for idx, (code, *_rest) in enumerate(CUSTOMERS)}
    suppliers = {code: idx + 1 for idx, (code, *_rest) in enumerate(SUPPLIERS)}
    products = {code: id_by_code("products", code) for code, *_rest in PRODUCTS}

    opening_entries = [
        ("1100", 75000), ("1210", 1250000), ("1300", 420000), ("1400", 900000),
        ("1600", 60000), ("1700", 15000), ("1810", 2000000), ("1820", 3500000),
        ("1830", 2800000), ("1850", 220000),
    ]
    opening_credits = [
        ("2100", 620000), ("2300", 120000), ("2500", 1800000), ("3100", 7500000), ("3300", 1200000),
    ]
    for code, amount in opening_entries:
        journal("2026-01-01", f"رصيد افتتاحي {code}", code, "1900", amount, "opening")
    for code, amount in opening_credits:
        journal("2026-01-01", f"رصيد افتتاحي {code}", "1900", code, amount, "opening")

    for code, _name, _unit, _cost, _sale, qty in PRODUCTS:
        if qty:
            cur.execute(
                "INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes) VALUES (?,?,?,?,?,?,?)",
                ("2026-01-01", products[code], "opening", qty, "opening", None, "رصيد افتتاحي مخزون"),
            )

    # Purchase order 1: received and invoiced.
    po1_lines = [
        (products["RM-STL-001"], 2000, 44, 88000, 14, 12320, 100320),
        (products["RM-PLA-001"], 1000, 29, 29000, 14, 4060, 33060),
    ]
    po1_total = sum(x[3] for x in po1_lines)
    po1_tax = sum(x[5] for x in po1_lines)
    cur.execute(
        """
        INSERT INTO purchase_orders(date,supplier_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total,payment_terms,delivery_date,delivery_terms,notes,status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("2026-02-03", suppliers["SUP-001"], po1_lines[0][0], 3000, po1_total / 3000, po1_total, 14, po1_tax, po1_total + po1_tax, "آجل 45 يوم", "2026-02-07", "توريد مخزن الخامات", "شراء خامات إنتاج شهر فبراير", "issued"),
    )
    po1 = cur.lastrowid
    for line in po1_lines:
        cur.execute("INSERT INTO purchase_order_lines(order_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total) VALUES (?,?,?,?,?,?,?,?)", (po1, *line))

    receipt_journal = journal("2026-02-07", "إذن استلام خامات GRN-000001", "1400", "2150", po1_total, "purchase_receipt", None, cc["PRD-01"])
    cur.execute(
        """
        INSERT INTO purchase_receipts(receipt_no,date,purchase_order_id,purchase_order_line_id,supplier_id,product_id,ordered_quantity,received_quantity,unit_price,total,tax_rate,tax_amount,grand_total,journal_id,status,invoice_id,notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("GRN-000001", "2026-02-07", po1, 1, suppliers["SUP-001"], po1_lines[0][0], 2000, 2000, 44, 88000, 14, 12320, 100320, receipt_journal, "invoiced", 1, "استلام صاج مجلفن"),
    )
    r1 = cur.lastrowid
    cur.execute(
        """
        INSERT INTO purchase_receipts(receipt_no,date,purchase_order_id,purchase_order_line_id,supplier_id,product_id,ordered_quantity,received_quantity,unit_price,total,tax_rate,tax_amount,grand_total,journal_id,status,invoice_id,notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("GRN-000002", "2026-02-07", po1, 2, suppliers["SUP-001"], po1_lines[1][0], 1000, 1000, 29, 29000, 14, 4060, 33060, receipt_journal, "invoiced", 1, "استلام حبيبات بلاستيك"),
    )
    r2 = cur.lastrowid
    for rid, product_code, qty in [(r1, "RM-STL-001", 2000), (r2, "RM-PLA-001", 1000)]:
        cur.execute("INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes) VALUES (?,?,?,?,?,?,?)", ("2026-02-07", products[product_code], "in", qty, "purchase_receipt", rid, "إذن استلام مشتريات"))

    pi_journal = journal("2026-02-08", "فاتورة مورد PI-000001 مقابل أذون استلام GRN-000001, GRN-000002", "2150", "2100", po1_total, "purchases")
    pi_tax_journal = journal("2026-02-08", "ضريبة فاتورة مورد PI-000001", "1500", "2100", po1_tax, "purchases")
    cur.execute(
        """
        INSERT INTO purchase_invoices(date,doc_no,supplier_invoice_no,supplier_invoice_date,due_date,supplier_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total,payment_type,journal_id,tax_journal_id,notes,status,purchase_order_id,purchase_receipt_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("2026-02-08", "PI-000001", "DST-5487", "2026-02-08", "2026-03-24", suppliers["SUP-001"], po1_lines[0][0], 1, po1_total, po1_total, 14, po1_tax, po1_total + po1_tax, "credit", pi_journal, pi_tax_journal, "فاتورة خامات صاج وبلاستيك", "posted", po1, r1),
    )
    pi1 = cur.lastrowid
    for product_id, qty, unit_price, total, *_rest in po1_lines:
        cur.execute("INSERT INTO purchase_invoice_lines(invoice_id,product_id,quantity,unit_price,total) VALUES (?,?,?,?,?)", (pi1, product_id, qty, unit_price, total))
    cur.execute("UPDATE journal SET source_id=? WHERE id IN (?,?)", (pi1, pi_journal, pi_tax_journal))
    cur.execute("UPDATE purchase_receipts SET invoice_id=? WHERE id IN (?,?)", (pi1, r1, r2))

    # Purchase order 2: received but not invoiced, for testing supplier invoice from GRN.
    cur.execute(
        """
        INSERT INTO purchase_orders(date,supplier_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total,payment_terms,delivery_date,delivery_terms,notes,status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("2026-03-10", suppliers["SUP-002"], products["RM-PNT-001"], 300, 92, 27600, 14, 3864, 31464, "آجل 30 يوم", "2026-03-15", "توريد مخزن الخامات", "أمر شراء دهانات صناعية", "issued"),
    )
    po2 = cur.lastrowid
    cur.execute("INSERT INTO purchase_order_lines(order_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total) VALUES (?,?,?,?,?,?,?,?)", (po2, products["RM-PNT-001"], 300, 92, 27600, 14, 3864, 31464))
    grn3_journal = journal("2026-03-15", "إذن استلام دهانات GRN-000003", "1400", "2150", 27600, "purchase_receipt", None, cc["PRD-02"])
    cur.execute(
        """
        INSERT INTO purchase_receipts(receipt_no,date,purchase_order_id,purchase_order_line_id,supplier_id,product_id,ordered_quantity,received_quantity,unit_price,total,tax_rate,tax_amount,grand_total,journal_id,status,invoice_id,notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("GRN-000003", "2026-03-15", po2, 3, suppliers["SUP-002"], products["RM-PNT-001"], 300, 300, 92, 27600, 14, 3864, 31464, grn3_journal, "received", None, "استلام متاح لاختبار فاتورة المورد"),
    )
    grn3 = cur.lastrowid
    cur.execute("INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes) VALUES (?,?,?,?,?,?,?)", ("2026-03-15", products["RM-PNT-001"], "in", 300, "purchase_receipt", grn3, "إذن استلام غير مفوتر"))

    # Production cycle.
    journal("2026-03-20", "صرف خامات مباشرة لأمر إنتاج MO-0001", "1420", "1400", 180000, "production", None, cc["PRD-01"])
    journal("2026-03-20", "تحميل أجور مباشرة على الإنتاج MO-0001", "1420", "2310", 40000, "production", None, cc["PRD-01"])
    journal("2026-03-25", "تحويل إنتاج تام من تحت التشغيل MO-0001", "1430", "1420", 220000, "production", None, cc["PRD-01"])
    for product_code, qty, movement_type, note in [
        ("RM-STL-001", -3500, "production_issue", "صرف خامات للإنتاج"),
        ("RM-PLA-001", -1200, "production_issue", "صرف خامات للإنتاج"),
        ("RM-PNT-001", -150, "production_issue", "صرف دهانات للإنتاج"),
        ("PKG-BOX-001", -2500, "production_issue", "صرف تعبئة للإنتاج"),
        ("FG-BOX-001", 450, "production_receipt", "استلام إنتاج تام"),
        ("FG-PNL-001", 120, "production_receipt", "استلام إنتاج تام"),
    ]:
        cur.execute("INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes) VALUES (?,?,?,?,?,?,?)", ("2026-03-25", products[product_code], movement_type, qty, "production", None, note))

    # Sales order 1: delivered and invoiced.
    so1_lines = [
        (products["FG-BOX-001"], 300, 950, 285000, 14, 39900, 324900),
        (products["FG-PNL-001"], 90, 1450, 130500, 14, 18270, 148770),
    ]
    so1_total = sum(x[3] for x in so1_lines)
    so1_tax = sum(x[5] for x in so1_lines)
    cur.execute(
        """
        INSERT INTO sales_orders(date,customer_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total,payment_terms,delivery_date,notes,status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("2026-04-01", customers["CUST-001"], so1_lines[0][0], 390, so1_total / 390, so1_total, 14, so1_tax, so1_total + so1_tax, "آجل 30 يوم", "2026-04-04", "أمر بيع توريدات كهربائية", "issued"),
    )
    so1 = cur.lastrowid
    for line in so1_lines:
        cur.execute("INSERT INTO sales_order_lines(order_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total) VALUES (?,?,?,?,?,?,?,?)", (so1, *line))
    cogs1 = 300 * 420 + 90 * 520
    dn_journal = journal("2026-04-04", "إذن صرف مبيعات DN-000001", "6100", "1400", cogs1, "sales_delivery", None, cc["SAL-01"])
    cur.execute(
        """
        INSERT INTO sales_delivery_notes(delivery_no,date,sales_order_id,sales_order_line_id,customer_id,product_id,ordered_quantity,delivered_quantity,unit_price,total,cost_total,tax_rate,tax_amount,grand_total,cogs_journal_id,status,invoice_id,notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("DN-000001", "2026-04-04", so1, 1, customers["CUST-001"], so1_lines[0][0], 300, 300, 950, 285000, 126000, 14, 39900, 324900, dn_journal, "invoiced", 1, "صرف صناديق معدنية"),
    )
    dn1 = cur.lastrowid
    cur.execute(
        """
        INSERT INTO sales_delivery_notes(delivery_no,date,sales_order_id,sales_order_line_id,customer_id,product_id,ordered_quantity,delivered_quantity,unit_price,total,cost_total,tax_rate,tax_amount,grand_total,cogs_journal_id,status,invoice_id,notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("DN-000002", "2026-04-04", so1, 2, customers["CUST-001"], so1_lines[1][0], 90, 90, 1450, 130500, 46800, 14, 18270, 148770, dn_journal, "invoiced", 1, "صرف لوحات توزيع"),
    )
    dn2 = cur.lastrowid
    for dn_id, product_code, qty in [(dn1, "FG-BOX-001", -300), (dn2, "FG-PNL-001", -90)]:
        cur.execute("INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes) VALUES (?,?,?,?,?,?,?)", ("2026-04-04", products[product_code], "out", qty, "sales_delivery", dn_id, "إذن صرف مبيعات"))

    si_journal = journal("2026-04-05", "فاتورة بيع SI-000001 من أذون صرف DN-000001, DN-000002", "1300", "4100", so1_total, "sales")
    si_tax_journal = journal("2026-04-05", "ضريبة فاتورة بيع SI-000001", "1300", "2200", so1_tax, "sales")
    cur.execute(
        """
        INSERT INTO sales_invoices(date,due_date,doc_no,customer_id,product_id,quantity,unit_price,total,cost_total,tax_rate,tax_amount,grand_total,payment_type,journal_id,tax_journal_id,cogs_journal_id,status,sales_order_id,sales_delivery_id,po_ref,gr_ref,notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("2026-04-05", "2026-05-05", "SI-000001", customers["CUST-001"], so1_lines[0][0], 1, so1_total, so1_total, cogs1, 14, so1_tax, so1_total + so1_tax, "credit", si_journal, si_tax_journal, None, "posted", so1, dn1, "PO-CUST-778", "DN-000001, DN-000002", "فاتورة توريدات مبيعات"),
    )
    si1 = cur.lastrowid
    for product_id, qty, unit_price, total, *_rest in so1_lines:
        cost = qty * (420 if product_id == products["FG-BOX-001"] else 520)
        cur.execute("INSERT INTO sales_invoice_lines(invoice_id,product_id,quantity,unit_price,total,cost_total) VALUES (?,?,?,?,?,?)", (si1, product_id, qty, unit_price, total, cost))
    cur.execute("UPDATE sales_delivery_notes SET invoice_id=? WHERE id IN (?,?)", (si1, dn1, dn2))
    cur.execute("UPDATE journal SET source_id=? WHERE id IN (?,?)", (si1, si_journal, si_tax_journal))

    # Sales order 2: delivered but not invoiced, appears in sales/from-delivery.
    cur.execute(
        """
        INSERT INTO sales_orders(date,customer_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total,payment_terms,delivery_date,notes,status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("2026-04-10", customers["CUST-002"], products["FG-BOX-001"], 50, 980, 49000, 14, 6860, 55860, "آجل 30 يوم", "2026-04-12", "أمر بيع مفتوح لاختبار الفوترة من إذن صرف", "issued"),
    )
    so2 = cur.lastrowid
    cur.execute("INSERT INTO sales_order_lines(order_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total) VALUES (?,?,?,?,?,?,?,?)", (so2, products["FG-BOX-001"], 50, 980, 49000, 14, 6860, 55860))
    dn3_cogs = 50 * 420
    dn3_journal = journal("2026-04-12", "إذن صرف مبيعات DN-000003 غير مفوتر", "6100", "1400", dn3_cogs, "sales_delivery", None, cc["SAL-01"])
    cur.execute(
        """
        INSERT INTO sales_delivery_notes(delivery_no,date,sales_order_id,sales_order_line_id,customer_id,product_id,ordered_quantity,delivered_quantity,unit_price,total,cost_total,tax_rate,tax_amount,grand_total,cogs_journal_id,status,invoice_id,notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("DN-000003", "2026-04-12", so2, 3, customers["CUST-002"], products["FG-BOX-001"], 50, 50, 980, 49000, dn3_cogs, 14, 6860, 55860, dn3_journal, "delivered", None, "إذن متاح لاختبار إنشاء فاتورة بيع"),
    )
    dn3 = cur.lastrowid
    cur.execute("INSERT INTO inventory_movements(date,product_id,movement_type,quantity,reference_type,reference_id,notes) VALUES (?,?,?,?,?,?,?)", ("2026-04-12", products["FG-BOX-001"], "out", -50, "sales_delivery", dn3, "إذن صرف غير مفوتر"))

    # Financial sales invoice.
    fin_total = 15000
    fin_tax = 2100
    fin_j = journal("2026-04-15", "فاتورة بيع مالية FSI-000001 - خدمات تركيب", "1300", "4500", fin_total, "sales")
    fin_tax_j = journal("2026-04-15", "ضريبة فاتورة بيع مالية FSI-000001", "1300", "2200", fin_tax, "sales")
    cur.execute(
        """
        INSERT INTO financial_sales_invoices(date,due_date,doc_no,customer_id,description,amount,tax_rate,tax_amount,grand_total,payment_type,revenue_account_id,journal_id,tax_journal_id,status,po_ref,gr_ref,notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("2026-04-15", "2026-05-15", "FSI-000001", customers["CUST-003"], "خدمات تركيب واختبار لوحات", fin_total, 14, fin_tax, fin_total + fin_tax, "credit", acc("4500"), fin_j, fin_tax_j, "posted", "PO-SVC-44", "SRV-APR", "فاتورة خدمات مالية بدون مخزون"),
    )
    fsi1 = cur.lastrowid
    cur.execute("INSERT INTO financial_sales_invoice_lines(invoice_id,description,amount) VALUES (?,?,?)", (fsi1, "خدمات تركيب", 10000))
    cur.execute("INSERT INTO financial_sales_invoice_lines(invoice_id,description,amount) VALUES (?,?,?)", (fsi1, "اختبار وتشغيل", 5000))
    cur.execute("UPDATE journal SET source_id=? WHERE id IN (?,?)", (fsi1, fin_j, fin_tax_j))

    # Cash, supplier, payroll, and operating expenses.
    rv_j = journal("2026-04-20", "سند قبض RV-000001 من شركة النور", "1210", "1300", 180000, "receipts")
    cur.execute("INSERT INTO receipt_vouchers(date,customer_id,amount,notes,journal_id,status) VALUES (?,?,?,?,?,?)", ("2026-04-20", customers["CUST-001"], 180000, "تحصيل جزئي من فاتورة SI-000001", rv_j, "posted"))
    rv1 = cur.lastrowid
    cur.execute("UPDATE journal SET source_id=? WHERE id=?", (rv1, rv_j))
    cur.execute("INSERT INTO invoice_allocations(allocation_type,invoice_id,voucher_id,amount) VALUES (?,?,?,?)", ("customer", si1, rv1, 180000))

    pv_j = journal("2026-04-22", "سند صرف PV-000001 إلى دلتا ستيل", "2100", "1210", 90000, "payments")
    cur.execute("INSERT INTO payment_vouchers(date,supplier_id,amount,notes,journal_id,status) VALUES (?,?,?,?,?,?)", ("2026-04-22", suppliers["SUP-001"], 90000, "سداد جزئي من فاتورة PI-000001", pv_j, "posted"))
    pv1 = cur.lastrowid
    cur.execute("UPDATE journal SET source_id=? WHERE id=?", (pv1, pv_j))
    cur.execute("INSERT INTO invoice_allocations(allocation_type,invoice_id,voucher_id,amount) VALUES (?,?,?,?)", ("supplier", pi1, pv1, 90000))

    employees = [
        ("EMP-001", "أحمد عبدالعزيز", "الإنتاج", "مشرف خط إنتاج", "2024-02-01", 14000, 2500, 1150, 1700, 850, "active", ""),
        ("EMP-002", "محمد سمير", "الإنتاج", "فني تشغيل", "2023-05-10", 9000, 1200, 760, 1150, 420, "active", ""),
        ("EMP-003", "سارة محمود", "الإدارة المالية", "محاسب موردين", "2022-08-15", 12000, 1800, 980, 1400, 650, "active", ""),
        ("EMP-004", "نهى جمال", "المبيعات", "مسؤول مبيعات", "2025-01-05", 10000, 1500, 820, 1250, 520, "active", ""),
    ]
    cur.executemany(
        """
        INSERT INTO employees(code,name,department,job_title,hire_date,base_salary,allowances,insurance_employee,insurance_company,tax,status,notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        employees,
    )
    gross = sum(row[5] + row[6] for row in employees)
    employee_deductions = sum(row[7] + row[9] for row in employees)
    company_insurance = sum(row[8] for row in employees)
    net = gross - employee_deductions
    prj1 = journal("2026-04-30", "إثبات صافي مرتبات أبريل 2026", "5110", "2310", net, "payroll", None, cc["ADM-01"])
    prj2 = journal("2026-04-30", "استقطاعات تأمينات العاملين أبريل 2026", "5110", "2220", sum(row[7] for row in employees), "payroll", None, cc["ADM-01"])
    prj3 = journal("2026-04-30", "ضريبة كسب عمل أبريل 2026", "5110", "2340", sum(row[9] for row in employees), "payroll", None, cc["ADM-01"])
    prj4 = journal("2026-04-30", "حصة الشركة في التأمينات أبريل 2026", "5170", "2220", company_insurance, "payroll", None, cc["ADM-01"])
    cur.execute(
        """
        INSERT INTO payroll_runs(period,date,total_gross,total_employee_deductions,total_company_insurance,total_net,status,journal_id,tax_journal_id,insurance_journal_id,company_insurance_journal_id,notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        ("2026-04", "2026-04-30", gross, employee_deductions, company_insurance, net, "posted", prj1, prj3, prj2, prj4, "رواتب شهر أبريل لشركة صناعية"),
    )
    payroll_run = cur.lastrowid
    cur.execute("SELECT id,base_salary,allowances,insurance_employee,insurance_company,tax FROM employees ORDER BY id")
    for emp_id, base_salary, allowances, ins_emp, ins_comp, tax in cur.fetchall():
        emp_gross = base_salary + allowances
        emp_net = emp_gross - ins_emp - tax
        cur.execute(
            """
            INSERT INTO payroll_lines(run_id,employee_id,base_salary,allowances,insurance_employee,insurance_company,tax,other_deductions,gross_salary,net_salary)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (payroll_run, emp_id, base_salary, allowances, ins_emp, ins_comp, tax, 0, emp_gross, emp_net),
        )
    cur.execute("UPDATE journal SET source_id=? WHERE id IN (?,?,?,?)", (payroll_run, prj1, prj2, prj3, prj4))

    for date_value, desc, debit, credit, amount, center in [
        ("2026-04-06", "إيجار إداري أبريل", "5120", "1210", 30000, "ADM-01"),
        ("2026-04-08", "كهرباء المصنع أبريل", "6410", "2320", 25000, "PRD-01"),
        ("2026-04-09", "صيانة دورية للآلات", "6420", "1210", 18000, "PRD-02"),
        ("2026-04-13", "دعاية وإعلان حملة أبريل", "5220", "1210", 18000, "SAL-01"),
        ("2026-04-18", "فوائد بنكية على قرض", "5310", "1210", 12000, "ADM-01"),
        ("2026-04-21", "مصروفات بنكية", "5320", "1210", 1800, "ADM-01"),
        ("2026-04-25", "مستلزمات تشغيل", "6440", "1210", 9500, "PRD-01"),
    ]:
        journal(date_value, desc, debit, credit, amount, "manual", None, cc[center])

    for doc_type, prefix, next_number in [
        ("sales", "SI", 2),
        ("purchases", "PI", 2),
        ("receipts", "RV", 2),
        ("payments", "PV", 2),
        ("sales_returns", "SR", 1),
        ("purchase_returns", "PR", 1),
        ("sales_orders", "SO", 3),
        ("sales_delivery_notes", "DN", 4),
        ("purchase_receipts", "GRN", 4),
        ("financial_sales", "FSI", 2),
        ("payroll", "PY", 2),
    ]:
        cur.execute("INSERT INTO document_sequences(doc_type,prefix,next_number) VALUES (?,?,?)", (doc_type, prefix, next_number))

    for group_key, group_name in [
        ("manual_journal", "القيود اليومية"),
        ("sales", "فواتير البيع"),
        ("purchases", "فواتير الموردين"),
        ("receipts", "سندات القبض"),
        ("payments", "سندات الصرف"),
    ]:
        cur.execute(
            "INSERT INTO posting_control(group_key,group_name,is_posted,posted_at,posted_by) VALUES (?,?,1,CURRENT_TIMESTAMP,'admin')",
            (group_key, group_name),
        )

    for period, start_date, end_date in [
        ("2026-01", "2026-01-01", "2026-01-31"),
        ("2026-02", "2026-02-01", "2026-02-28"),
        ("2026-03", "2026-03-01", "2026-03-31"),
        ("2026-04", "2026-04-01", "2026-04-30"),
        ("2026-05", "2026-05-01", "2026-05-31"),
    ]:
        cur.execute("INSERT INTO fiscal_periods(name,start_date,end_date,status,notes) VALUES (?,?,?,?,?)", (period, start_date, end_date, "open", "فترة اختبار مفتوحة"))

    cur.execute(
        "INSERT INTO audit_log(username,action,entity_type,details) VALUES (?,?,?,?)",
        ("admin", "reset", "industrial_demo_data", "تحميل بيانات اختبار فعلية لشركة صناعية"),
    )

    cur.execute("DELETE FROM ledger")
    cur.execute(
        "SELECT id,date,description,debit_account_id,credit_account_id,amount FROM journal WHERE status='posted' ORDER BY id"
    )
    for jid, date_value, desc, debit_id, credit_id, amount in cur.fetchall():
        cur.execute(
            "INSERT INTO ledger(account_id,date,description,debit,credit,journal_id) VALUES (?,?,?,?,?,?)",
            (debit_id, date_value, desc, amount, 0, jid),
        )
        cur.execute(
            "INSERT INTO ledger(account_id,date,description,debit,credit,journal_id) VALUES (?,?,?,?,?,?)",
            (credit_id, date_value, desc, 0, amount, jid),
        )

    conn.commit()

    print("تم تحميل بيانات شركة صناعية تجريبية.")
    if backup_path:
        print(f"نسخة احتياطية: {backup_path}")
    for table in [
        "accounts", "customers", "suppliers", "products", "journal", "ledger",
        "purchase_orders", "purchase_receipts", "purchase_invoices",
        "sales_orders", "sales_delivery_notes", "sales_invoices",
        "financial_sales_invoices", "receipt_vouchers", "payment_vouchers",
        "employees", "payroll_runs",
    ]:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"{table}: {cur.fetchone()[0]}")
    cur.execute("SELECT ROUND(SUM(debit)-SUM(credit),2) FROM ledger")
    print(f"فرق ميزان المراجعة: {cur.fetchone()[0] or 0}")
    conn.close()


if __name__ == "__main__":
    main()
