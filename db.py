import os
import secrets
import sqlite3

from werkzeug.security import generate_password_hash


DEFAULT_ACCOUNTS = [
    ("1000", "الأصول", "أصول"),
    ("1100", "الخزنة", "أصول"),
    ("1110", "خزنة المصنع", "أصول"),
    ("1120", "خزنة الإدارة", "أصول"),
    ("1200", "البنك", "أصول"),
    ("1210", "حساب جاري بالبنك", "أصول"),
    ("1220", "ودائع بنكية", "أصول"),
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
    ("1510", "ضريبة خصم وإضافة مدينة", "أصول"),
    ("1600", "مصروفات مقدمة", "أصول"),
    ("1700", "عهد وسلف عاملين", "أصول"),
    ("1900", "أرصدة افتتاحية وتسويات", "أصول"),
    ("1800", "الأصول الثابتة", "أصول"),
    ("1810", "أراضي", "أصول"),
    ("1820", "مباني وإنشاءات", "أصول"),
    ("1830", "آلات ومعدات إنتاج", "أصول"),
    ("1840", "سيارات ووسائل نقل", "أصول"),
    ("1850", "أثاث وأجهزة مكتبية", "أصول"),
    ("1860", "مجمع إهلاك الأصول الثابتة", "أصول"),
    ("2000", "الخصوم", "خصوم"),
    ("2100", "الموردون", "خصوم"),
    ("2110", "موردو خامات", "خصوم"),
    ("2120", "موردو خدمات", "خصوم"),
    ("2130", "أوراق دفع", "خصوم"),
    ("2150", "بضاعة مستلمة غير مفوترة", "خصوم"),
    ("2200", "ضريبة قيمة مضافة - مخرجات", "خصوم"),
    ("2230", "ضريبة خصم وإضافة دائنة", "خصوم"),
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
    ("3500", "أرباح مرحلة", "حقوق ملكية"),
    ("4000", "الإيرادات", "إيرادات"),
    ("4100", "إيرادات المبيعات", "إيرادات"),
    ("4110", "مبيعات محلية", "إيرادات"),
    ("4120", "مبيعات تصدير", "إيرادات"),
    ("4200", "مردودات ومسموحات المبيعات", "إيرادات"),
    ("4210", "مردودات ومسموحات المشتريات", "إيرادات"),
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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
BOOTSTRAP_CREDENTIALS_FILE = os.path.join(INSTANCE_DIR, "initial_admin_credentials.txt")

PERMISSION_MODULES = [
    ("accounting", "الحسابات العامة"),
    ("customers", "العملاء"),
    ("suppliers", "الموردون"),
    ("inventory", "المخازن والأصناف"),
    ("sales", "المبيعات"),
    ("purchases", "المشتريات"),
    ("receipts", "سندات القبض"),
    ("payments", "سندات الصرف"),
    ("hr", "شؤون العاملين"),
    ("reports", "التقارير"),
    ("e_invoices", "الفاتورة الإلكترونية"),
]

DEFAULT_ROLE_PERMISSIONS = {
    "accountant": {
        "accounting": "write",
        "customers": "write",
        "suppliers": "write",
        "inventory": "write",
        "sales": "write",
        "purchases": "write",
        "receipts": "write",
        "payments": "write",
        "hr": "write",
        "reports": "read",
        "e_invoices": "write",
    },
    "sales": {
        "customers": "write",
        "inventory": "read",
        "sales": "write",
        "receipts": "write",
        "reports": "read",
    },
    "viewer": {
        "accounting": "read",
        "customers": "read",
        "suppliers": "read",
        "inventory": "read",
        "sales": "read",
        "purchases": "read",
        "receipts": "read",
        "payments": "read",
        "hr": "read",
        "reports": "read",
        "e_invoices": "read",
    },
}


def add_column_if_missing(cur, table, column, definition):
    cur.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cur.fetchall()]
    if column not in columns:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cur = conn.cursor()

    cur.execute("PRAGMA foreign_keys = ON")
    cur.execute("PRAGMA busy_timeout = 30000")
    cur.execute("PRAGMA journal_mode = WAL")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT NOT NULL DEFAULT 'admin'
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS company_settings(
            id INTEGER PRIMARY KEY CHECK(id = 1),
            company_name TEXT NOT NULL DEFAULT 'شركة تجريبية للصناعات',
            tax_number TEXT,
            commercial_register TEXT,
            address TEXT,
            phone TEXT,
            email TEXT,
            logo_path TEXT,
            default_tax_rate REAL NOT NULL DEFAULT 14,
            invoice_footer TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS accounts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            name TEXT,
            type TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS journal(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            description TEXT NOT NULL,
            debit_account_id INTEGER NOT NULL,
            credit_account_id INTEGER NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            status TEXT NOT NULL DEFAULT 'posted',
            source_type TEXT NOT NULL DEFAULT 'manual',
            source_id INTEGER,
            cost_center_id INTEGER
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ledger(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            description TEXT NOT NULL,
            debit REAL NOT NULL DEFAULT 0,
            credit REAL NOT NULL DEFAULT 0,
            journal_id INTEGER NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS customers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            address TEXT,
            tax_registration_number TEXT,
            tax_card_number TEXT,
            commercial_register TEXT,
            contact_person TEXT,
            email TEXT,
            withholding_status TEXT NOT NULL DEFAULT 'non_subject'
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS suppliers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            address TEXT,
            tax_registration_number TEXT,
            tax_card_number TEXT,
            commercial_register TEXT,
            contact_person TEXT,
            email TEXT,
            withholding_status TEXT NOT NULL DEFAULT 'exempt'
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            name TEXT NOT NULL,
            unit TEXT NOT NULL DEFAULT 'وحدة',
            purchase_price REAL NOT NULL DEFAULT 0,
            sale_price REAL NOT NULL DEFAULT 0,
            stock_quantity REAL NOT NULL DEFAULT 0
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS product_categories(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_invoices(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            due_date TEXT,
            doc_no TEXT,
            customer_id INTEGER,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL CHECK(quantity > 0),
            unit_price REAL NOT NULL CHECK(unit_price >= 0),
            total REAL NOT NULL CHECK(total >= 0),
            cost_total REAL NOT NULL DEFAULT 0,
            tax_rate REAL NOT NULL DEFAULT 14,
            tax_amount REAL NOT NULL DEFAULT 0,
            withholding_rate REAL NOT NULL DEFAULT 0,
            withholding_amount REAL NOT NULL DEFAULT 0,
            grand_total REAL NOT NULL DEFAULT 0,
            payment_type TEXT NOT NULL DEFAULT 'cash',
            journal_id INTEGER,
            tax_journal_id INTEGER,
            withholding_journal_id INTEGER,
            cogs_journal_id INTEGER,
            status TEXT NOT NULL DEFAULT 'posted',
            cancelled_at TEXT,
            cancel_reason TEXT,
            po_ref TEXT,
            gr_ref TEXT,
            notes TEXT,
            FOREIGN KEY(customer_id) REFERENCES customers(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS financial_sales_invoices(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            due_date TEXT,
            doc_no TEXT,
            customer_id INTEGER,
            description TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount >= 0),
            tax_rate REAL NOT NULL DEFAULT 14,
            tax_amount REAL NOT NULL DEFAULT 0,
            withholding_rate REAL NOT NULL DEFAULT 0,
            withholding_amount REAL NOT NULL DEFAULT 0,
            grand_total REAL NOT NULL DEFAULT 0,
            payment_type TEXT NOT NULL DEFAULT 'credit',
            revenue_account_id INTEGER,
            journal_id INTEGER,
            tax_journal_id INTEGER,
            withholding_journal_id INTEGER,
            status TEXT NOT NULL DEFAULT 'posted',
            cancelled_at TEXT,
            cancel_reason TEXT,
            po_ref TEXT,
            gr_ref TEXT,
            notes TEXT,
            FOREIGN KEY(customer_id) REFERENCES customers(id),
            FOREIGN KEY(revenue_account_id) REFERENCES accounts(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS financial_sales_invoice_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount >= 0),
            FOREIGN KEY(invoice_id) REFERENCES financial_sales_invoices(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS purchase_invoices(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            supplier_invoice_no TEXT,
            supplier_invoice_date TEXT,
            due_date TEXT,
            supplier_id INTEGER,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL CHECK(quantity > 0),
            unit_price REAL NOT NULL CHECK(unit_price >= 0),
            total REAL NOT NULL CHECK(total >= 0),
            tax_rate REAL NOT NULL DEFAULT 14,
            tax_amount REAL NOT NULL DEFAULT 0,
            withholding_rate REAL NOT NULL DEFAULT 0,
            withholding_amount REAL NOT NULL DEFAULT 0,
            grand_total REAL NOT NULL DEFAULT 0,
            payment_type TEXT NOT NULL DEFAULT 'cash',
            journal_id INTEGER,
            tax_journal_id INTEGER,
            withholding_journal_id INTEGER,
            status TEXT NOT NULL DEFAULT 'posted',
            cancelled_at TEXT,
            cancel_reason TEXT,
            notes TEXT,
            doc_no TEXT,
            FOREIGN KEY(supplier_id) REFERENCES suppliers(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS cost_centers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            name TEXT NOT NULL,
            center_type TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            notes TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS document_sequences(
            doc_type TEXT PRIMARY KEY,
            prefix TEXT NOT NULL,
            next_number INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_invoice_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL CHECK(quantity > 0),
            unit_price REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL DEFAULT 0,
            cost_total REAL NOT NULL DEFAULT 0
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS purchase_invoice_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL CHECK(quantity > 0),
            unit_price REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL DEFAULT 0
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS invoice_allocations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            allocation_type TEXT NOT NULL,
            invoice_id INTEGER NOT NULL,
            voucher_id INTEGER NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_returns(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            sales_invoice_id INTEGER,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL CHECK(quantity > 0),
            unit_price REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL DEFAULT 0,
            tax_amount REAL NOT NULL DEFAULT 0,
            grand_total REAL NOT NULL DEFAULT 0,
            cost_total REAL NOT NULL DEFAULT 0,
            journal_id INTEGER,
            tax_journal_id INTEGER,
            cogs_journal_id INTEGER,
            status TEXT NOT NULL DEFAULT 'posted',
            po_ref TEXT,
            gr_ref TEXT,
            notes TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS purchase_returns(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            purchase_invoice_id INTEGER,
            supplier_id INTEGER,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL CHECK(quantity > 0),
            unit_price REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL DEFAULT 0,
            tax_amount REAL NOT NULL DEFAULT 0,
            grand_total REAL NOT NULL DEFAULT 0,
            journal_id INTEGER,
            tax_journal_id INTEGER,
            status TEXT NOT NULL DEFAULT 'posted',
            po_ref TEXT,
            gr_ref TEXT,
            notes TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_credit_notes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            doc_no TEXT UNIQUE,
            sales_return_id INTEGER NOT NULL UNIQUE,
            sales_invoice_id INTEGER,
            customer_id INTEGER,
            product_id INTEGER,
            quantity REAL NOT NULL DEFAULT 0,
            unit_price REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL DEFAULT 0,
            tax_amount REAL NOT NULL DEFAULT 0,
            grand_total REAL NOT NULL DEFAULT 0,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'posted',
            FOREIGN KEY(sales_return_id) REFERENCES sales_returns(id),
            FOREIGN KEY(sales_invoice_id) REFERENCES sales_invoices(id),
            FOREIGN KEY(customer_id) REFERENCES customers(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS supplier_debit_notes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            doc_no TEXT UNIQUE,
            purchase_return_id INTEGER NOT NULL UNIQUE,
            purchase_invoice_id INTEGER,
            supplier_id INTEGER,
            product_id INTEGER,
            quantity REAL NOT NULL DEFAULT 0,
            unit_price REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL DEFAULT 0,
            tax_amount REAL NOT NULL DEFAULT 0,
            grand_total REAL NOT NULL DEFAULT 0,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'posted',
            FOREIGN KEY(purchase_return_id) REFERENCES purchase_returns(id),
            FOREIGN KEY(purchase_invoice_id) REFERENCES purchase_invoices(id),
            FOREIGN KEY(supplier_id) REFERENCES suppliers(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_adjustments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            doc_no TEXT UNIQUE,
            customer_id INTEGER NOT NULL,
            adjustment_type TEXT NOT NULL,
            related_invoice_id INTEGER,
            description TEXT NOT NULL,
            total REAL NOT NULL DEFAULT 0,
            tax_rate REAL NOT NULL DEFAULT 14,
            tax_amount REAL NOT NULL DEFAULT 0,
            grand_total REAL NOT NULL DEFAULT 0,
            journal_id INTEGER,
            tax_journal_id INTEGER,
            status TEXT NOT NULL DEFAULT 'posted',
            notes TEXT,
            FOREIGN KEY(customer_id) REFERENCES customers(id),
            FOREIGN KEY(related_invoice_id) REFERENCES sales_invoices(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS year_end_closings(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fiscal_year TEXT NOT NULL UNIQUE,
            closing_date TEXT NOT NULL,
            revenue_total REAL NOT NULL DEFAULT 0,
            expense_total REAL NOT NULL DEFAULT 0,
            net_income REAL NOT NULL DEFAULT 0,
            journal_id INTEGER,
            status TEXT NOT NULL DEFAULT 'posted',
            notes TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS purchase_orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            supplier_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL CHECK(quantity > 0),
            unit_price REAL NOT NULL CHECK(unit_price >= 0),
            total REAL NOT NULL CHECK(total >= 0),
            tax_rate REAL NOT NULL DEFAULT 14,
            tax_amount REAL NOT NULL DEFAULT 0,
            grand_total REAL NOT NULL DEFAULT 0,
            payment_terms TEXT,
            delivery_date TEXT,
            delivery_terms TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            notes TEXT,
            FOREIGN KEY(supplier_id) REFERENCES suppliers(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS purchase_order_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL CHECK(quantity > 0),
            unit_price REAL NOT NULL CHECK(unit_price >= 0),
            total REAL NOT NULL DEFAULT 0,
            tax_rate REAL NOT NULL DEFAULT 14,
            tax_amount REAL NOT NULL DEFAULT 0,
            grand_total REAL NOT NULL DEFAULT 0,
            FOREIGN KEY(order_id) REFERENCES purchase_orders(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            customer_id INTEGER,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL CHECK(quantity > 0),
            unit_price REAL NOT NULL CHECK(unit_price >= 0),
            total REAL NOT NULL DEFAULT 0,
            tax_rate REAL NOT NULL DEFAULT 14,
            tax_amount REAL NOT NULL DEFAULT 0,
            grand_total REAL NOT NULL DEFAULT 0,
            payment_terms TEXT,
            delivery_date TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'issued',
            FOREIGN KEY(customer_id) REFERENCES customers(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_order_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL CHECK(quantity > 0),
            unit_price REAL NOT NULL CHECK(unit_price >= 0),
            total REAL NOT NULL DEFAULT 0,
            tax_rate REAL NOT NULL DEFAULT 14,
            tax_amount REAL NOT NULL DEFAULT 0,
            grand_total REAL NOT NULL DEFAULT 0,
            FOREIGN KEY(order_id) REFERENCES sales_orders(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_delivery_notes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            delivery_no TEXT UNIQUE,
            date TEXT NOT NULL,
            sales_order_id INTEGER NOT NULL,
            customer_id INTEGER,
            product_id INTEGER NOT NULL,
            ordered_quantity REAL NOT NULL DEFAULT 0,
            delivered_quantity REAL NOT NULL CHECK(delivered_quantity > 0),
            unit_price REAL NOT NULL CHECK(unit_price >= 0),
            total REAL NOT NULL DEFAULT 0,
            cost_total REAL NOT NULL DEFAULT 0,
            tax_rate REAL NOT NULL DEFAULT 14,
            tax_amount REAL NOT NULL DEFAULT 0,
            grand_total REAL NOT NULL DEFAULT 0,
            cogs_journal_id INTEGER,
            status TEXT NOT NULL DEFAULT 'delivered',
            invoice_id INTEGER,
            notes TEXT,
            FOREIGN KEY(sales_order_id) REFERENCES sales_orders(id),
            FOREIGN KEY(customer_id) REFERENCES customers(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS purchase_receipts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_no TEXT UNIQUE,
            date TEXT NOT NULL,
            purchase_order_id INTEGER NOT NULL,
            supplier_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            ordered_quantity REAL NOT NULL DEFAULT 0,
            received_quantity REAL NOT NULL CHECK(received_quantity > 0),
            unit_price REAL NOT NULL CHECK(unit_price >= 0),
            total REAL NOT NULL DEFAULT 0,
            tax_rate REAL NOT NULL DEFAULT 14,
            tax_amount REAL NOT NULL DEFAULT 0,
            grand_total REAL NOT NULL DEFAULT 0,
            journal_id INTEGER,
            status TEXT NOT NULL DEFAULT 'received',
            invoice_id INTEGER,
            notes TEXT,
            FOREIGN KEY(purchase_order_id) REFERENCES purchase_orders(id),
            FOREIGN KEY(supplier_id) REFERENCES suppliers(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS inventory_movements(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            movement_type TEXT NOT NULL,
            quantity REAL NOT NULL,
            reference_type TEXT,
            reference_id INTEGER,
            notes TEXT,
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS receipt_vouchers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            customer_id INTEGER NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            notes TEXT,
            journal_id INTEGER,
            status TEXT NOT NULL DEFAULT 'posted',
            cancelled_at TEXT,
            cancel_reason TEXT,
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS payment_vouchers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            supplier_id INTEGER NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            notes TEXT,
            journal_id INTEGER,
            status TEXT NOT NULL DEFAULT 'posted',
            cancelled_at TEXT,
            cancel_reason TEXT,
            FOREIGN KEY(supplier_id) REFERENCES suppliers(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS employees(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            name TEXT NOT NULL,
            department TEXT,
            job_title TEXT,
            hire_date TEXT,
            base_salary REAL NOT NULL DEFAULT 0,
            allowances REAL NOT NULL DEFAULT 0,
            insurance_employee REAL NOT NULL DEFAULT 0,
            insurance_company REAL NOT NULL DEFAULT 0,
            tax REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active',
            notes TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS payroll_runs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period TEXT NOT NULL,
            date TEXT NOT NULL,
            total_gross REAL NOT NULL DEFAULT 0,
            total_employee_deductions REAL NOT NULL DEFAULT 0,
            total_company_insurance REAL NOT NULL DEFAULT 0,
            total_net REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'posted',
            journal_id INTEGER,
            tax_journal_id INTEGER,
            insurance_journal_id INTEGER,
            company_insurance_journal_id INTEGER,
            notes TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS payroll_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            base_salary REAL NOT NULL DEFAULT 0,
            allowances REAL NOT NULL DEFAULT 0,
            insurance_employee REAL NOT NULL DEFAULT 0,
            insurance_company REAL NOT NULL DEFAULT 0,
            tax REAL NOT NULL DEFAULT 0,
            other_deductions REAL NOT NULL DEFAULT 0,
            gross_salary REAL NOT NULL DEFAULT 0,
            net_salary REAL NOT NULL DEFAULT 0,
            FOREIGN KEY(run_id) REFERENCES payroll_runs(id),
            FOREIGN KEY(employee_id) REFERENCES employees(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            username TEXT,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            details TEXT,
            old_values TEXT,
            new_values TEXT,
            ip_address TEXT,
            user_agent TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS role_permissions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            permission_key TEXT NOT NULL,
            access_level TEXT NOT NULL DEFAULT 'none',
            UNIQUE(role, permission_key)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS posting_control(
            group_key TEXT PRIMARY KEY,
            group_name TEXT NOT NULL,
            is_posted INTEGER NOT NULL DEFAULT 1,
            posted_at TEXT,
            posted_by TEXT,
            unposted_at TEXT,
            unposted_by TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS fiscal_periods(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            closed_at TEXT,
            closed_by TEXT,
            reopened_at TEXT,
            reopened_by TEXT,
            notes TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS e_invoice_documents(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_type TEXT NOT NULL,
            document_id INTEGER NOT NULL,
            eta_uuid TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            payload_json TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT
        )
        """
    )

    add_column_if_missing(cur, "users", "role", "TEXT NOT NULL DEFAULT 'admin'")
    add_column_if_missing(cur, "company_settings", "tax_number", "TEXT")
    add_column_if_missing(cur, "company_settings", "commercial_register", "TEXT")
    add_column_if_missing(cur, "company_settings", "address", "TEXT")
    add_column_if_missing(cur, "company_settings", "phone", "TEXT")
    add_column_if_missing(cur, "company_settings", "email", "TEXT")
    add_column_if_missing(cur, "company_settings", "logo_path", "TEXT")
    add_column_if_missing(cur, "company_settings", "default_tax_rate", "REAL NOT NULL DEFAULT 14")
    add_column_if_missing(cur, "company_settings", "invoice_footer", "TEXT")
    add_column_if_missing(cur, "journal", "status", "TEXT NOT NULL DEFAULT 'posted'")
    add_column_if_missing(cur, "journal", "source_type", "TEXT NOT NULL DEFAULT 'manual'")
    add_column_if_missing(cur, "journal", "source_id", "INTEGER")
    add_column_if_missing(cur, "journal", "cost_center_id", "INTEGER")
    for party_table in ("customers", "suppliers"):
        add_column_if_missing(cur, party_table, "tax_registration_number", "TEXT")
        add_column_if_missing(cur, party_table, "tax_card_number", "TEXT")
        add_column_if_missing(cur, party_table, "commercial_register", "TEXT")
        add_column_if_missing(cur, party_table, "contact_person", "TEXT")
        add_column_if_missing(cur, party_table, "email", "TEXT")
    add_column_if_missing(cur, "customers", "withholding_status", "TEXT NOT NULL DEFAULT 'non_subject'")
    add_column_if_missing(cur, "suppliers", "withholding_status", "TEXT NOT NULL DEFAULT 'exempt'")
    add_column_if_missing(cur, "audit_log", "old_values", "TEXT")
    add_column_if_missing(cur, "audit_log", "new_values", "TEXT")
    add_column_if_missing(cur, "audit_log", "ip_address", "TEXT")
    add_column_if_missing(cur, "audit_log", "user_agent", "TEXT")
    add_column_if_missing(cur, "sales_invoices", "payment_type", "TEXT NOT NULL DEFAULT 'cash'")
    add_column_if_missing(cur, "sales_invoices", "due_date", "TEXT")
    add_column_if_missing(cur, "sales_invoices", "doc_no", "TEXT")
    add_column_if_missing(cur, "sales_invoices", "cost_total", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "sales_invoices", "tax_rate", "REAL NOT NULL DEFAULT 14")
    add_column_if_missing(cur, "sales_invoices", "tax_amount", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "sales_invoices", "withholding_rate", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "sales_invoices", "withholding_amount", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "sales_invoices", "grand_total", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "sales_invoices", "tax_journal_id", "INTEGER")
    add_column_if_missing(cur, "sales_invoices", "withholding_journal_id", "INTEGER")
    add_column_if_missing(cur, "sales_invoices", "cogs_journal_id", "INTEGER")
    add_column_if_missing(cur, "sales_invoices", "status", "TEXT NOT NULL DEFAULT 'posted'")
    add_column_if_missing(cur, "sales_invoices", "cancelled_at", "TEXT")
    add_column_if_missing(cur, "sales_invoices", "cancel_reason", "TEXT")
    add_column_if_missing(cur, "sales_invoices", "sales_order_id", "INTEGER")
    add_column_if_missing(cur, "sales_invoices", "sales_delivery_id", "INTEGER")
    add_column_if_missing(cur, "sales_invoices", "po_ref", "TEXT")
    add_column_if_missing(cur, "sales_invoices", "gr_ref", "TEXT")
    add_column_if_missing(cur, "sales_invoices", "notes", "TEXT")
    add_column_if_missing(cur, "sales_delivery_notes", "sales_order_line_id", "INTEGER")
    add_column_if_missing(cur, "sales_delivery_notes", "cancelled_at", "TEXT")
    add_column_if_missing(cur, "sales_delivery_notes", "cancel_reason", "TEXT")
    add_column_if_missing(cur, "sales_returns", "po_ref", "TEXT")
    add_column_if_missing(cur, "sales_returns", "gr_ref", "TEXT")
    add_column_if_missing(cur, "purchase_returns", "po_ref", "TEXT")
    add_column_if_missing(cur, "purchase_returns", "gr_ref", "TEXT")
    add_column_if_missing(cur, "purchase_invoices", "payment_type", "TEXT NOT NULL DEFAULT 'cash'")
    add_column_if_missing(cur, "purchase_invoices", "tax_rate", "REAL NOT NULL DEFAULT 14")
    add_column_if_missing(cur, "purchase_invoices", "tax_amount", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "purchase_invoices", "withholding_rate", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "purchase_invoices", "withholding_amount", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "purchase_invoices", "grand_total", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "purchase_invoices", "tax_journal_id", "INTEGER")
    add_column_if_missing(cur, "purchase_invoices", "withholding_journal_id", "INTEGER")
    add_column_if_missing(cur, "purchase_invoices", "status", "TEXT NOT NULL DEFAULT 'posted'")
    add_column_if_missing(cur, "purchase_invoices", "cancelled_at", "TEXT")
    add_column_if_missing(cur, "purchase_invoices", "cancel_reason", "TEXT")
    add_column_if_missing(cur, "purchase_invoices", "supplier_invoice_no", "TEXT")
    add_column_if_missing(cur, "purchase_invoices", "supplier_invoice_date", "TEXT")
    add_column_if_missing(cur, "purchase_invoices", "due_date", "TEXT")
    add_column_if_missing(cur, "purchase_invoices", "notes", "TEXT")
    add_column_if_missing(cur, "purchase_invoices", "doc_no", "TEXT")
    add_column_if_missing(cur, "purchase_invoices", "purchase_order_id", "INTEGER")
    add_column_if_missing(cur, "purchase_invoices", "purchase_receipt_id", "INTEGER")
    add_column_if_missing(cur, "purchase_receipts", "cancelled_at", "TEXT")
    add_column_if_missing(cur, "purchase_receipts", "cancel_reason", "TEXT")
    add_column_if_missing(cur, "financial_sales_invoices", "withholding_rate", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "financial_sales_invoices", "withholding_amount", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "financial_sales_invoices", "withholding_journal_id", "INTEGER")
    add_column_if_missing(cur, "purchase_receipts", "purchase_order_line_id", "INTEGER")
    add_column_if_missing(cur, "products", "default_supplier_id", "INTEGER")
    add_column_if_missing(cur, "products", "category_id", "INTEGER")
    add_column_if_missing(cur, "products", "barcode_value", "TEXT")
    add_column_if_missing(cur, "products", "barcode_payload", "TEXT")
    add_column_if_missing(cur, "receipt_vouchers", "status", "TEXT NOT NULL DEFAULT 'posted'")
    add_column_if_missing(cur, "receipt_vouchers", "cancelled_at", "TEXT")
    add_column_if_missing(cur, "receipt_vouchers", "cancel_reason", "TEXT")
    add_column_if_missing(cur, "payment_vouchers", "status", "TEXT NOT NULL DEFAULT 'posted'")
    add_column_if_missing(cur, "payment_vouchers", "cancelled_at", "TEXT")
    add_column_if_missing(cur, "payment_vouchers", "cancel_reason", "TEXT")
    add_column_if_missing(cur, "employees", "code", "TEXT")
    add_column_if_missing(cur, "employees", "department", "TEXT")
    add_column_if_missing(cur, "employees", "job_title", "TEXT")
    add_column_if_missing(cur, "employees", "hire_date", "TEXT")
    add_column_if_missing(cur, "employees", "base_salary", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "employees", "allowances", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "employees", "insurance_employee", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "employees", "insurance_company", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "employees", "tax", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "employees", "status", "TEXT NOT NULL DEFAULT 'active'")
    add_column_if_missing(cur, "employees", "notes", "TEXT")

    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_products_barcode_value ON products(barcode_value)")

    cur.execute("UPDATE sales_invoices SET grand_total=total + tax_amount WHERE grand_total=0")
    cur.execute("UPDATE purchase_invoices SET grand_total=total + tax_amount WHERE grand_total=0")
    cur.execute(
        """
        INSERT INTO sales_order_lines(order_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total)
        SELECT so.id,so.product_id,so.quantity,so.unit_price,so.total,so.tax_rate,so.tax_amount,so.grand_total
        FROM sales_orders so
        WHERE NOT EXISTS (SELECT 1 FROM sales_order_lines sol WHERE sol.order_id=so.id)
        """
    )
    cur.execute(
        """
        INSERT INTO purchase_order_lines(order_id,product_id,quantity,unit_price,total,tax_rate,tax_amount,grand_total)
        SELECT po.id,po.product_id,po.quantity,po.unit_price,po.total,po.tax_rate,po.tax_amount,po.grand_total
        FROM purchase_orders po
        WHERE NOT EXISTS (SELECT 1 FROM purchase_order_lines pol WHERE pol.order_id=po.id)
        """
    )
    cur.execute(
        """
        UPDATE sales_delivery_notes
        SET sales_order_line_id=(
            SELECT sol.id
            FROM sales_order_lines sol
            WHERE sol.order_id=sales_delivery_notes.sales_order_id
              AND sol.product_id=sales_delivery_notes.product_id
            ORDER BY sol.id
            LIMIT 1
        )
        WHERE sales_order_line_id IS NULL
        """
    )
    cur.execute(
        """
        UPDATE purchase_receipts
        SET purchase_order_line_id=(
            SELECT pol.id
            FROM purchase_order_lines pol
            WHERE pol.order_id=purchase_receipts.purchase_order_id
              AND pol.product_id=purchase_receipts.product_id
            ORDER BY pol.id
            LIMIT 1
        )
        WHERE purchase_order_line_id IS NULL
        """
    )

    for doc_type, prefix in [
        ("sales", "SI"),
        ("purchases", "PI"),
        ("receipts", "RV"),
        ("payments", "PV"),
        ("sales_returns", "SR"),
        ("sales_orders", "SO"),
        ("sales_delivery_notes", "DN"),
        ("financial_sales", "FSI"),
        ("purchase_returns", "PR"),
        ("purchase_receipts", "GRN"),
        ("sales_credit_notes", "SCN"),
        ("supplier_debit_notes", "SDN"),
        ("customer_adjustments", "ADJ"),
        ("payroll", "PY"),
    ]:
        cur.execute("SELECT doc_type FROM document_sequences WHERE doc_type=?", (doc_type,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO document_sequences(doc_type,prefix,next_number) VALUES (?,?,1)",
                (doc_type, prefix),
            )

    posting_groups = [
        ("manual_journal", "القيود اليومية"),
        ("sales", "فواتير البيع"),
        ("purchases", "فواتير الموردين"),
        ("receipts", "سندات القبض"),
        ("payments", "سندات الصرف"),
    ]
    for group_key, group_name in posting_groups:
        cur.execute("SELECT group_key FROM posting_control WHERE group_key=?", (group_key,))
        if cur.fetchone():
            cur.execute("UPDATE posting_control SET group_name=? WHERE group_key=?", (group_name, group_key))
        else:
            cur.execute(
                "INSERT INTO posting_control(group_key,group_name,is_posted,posted_at,posted_by) VALUES (?,?,1,CURRENT_TIMESTAMP,'system')",
                (group_key, group_name),
            )

    cur.execute("UPDATE journal SET status='posted' WHERE status IS NULL OR status=''")
    cur.execute("UPDATE journal SET source_type='manual' WHERE source_type IS NULL OR source_type=''")
    cur.execute("UPDATE journal SET source_type='auto' WHERE description LIKE 'قيد عكسي%'")
    cur.execute(
        """
        UPDATE journal
        SET source_type='sales',
            source_id=(SELECT id FROM sales_invoices WHERE journal_id=journal.id OR tax_journal_id=journal.id OR cogs_journal_id=journal.id)
        WHERE id IN (
            SELECT journal_id FROM sales_invoices WHERE journal_id IS NOT NULL
            UNION SELECT tax_journal_id FROM sales_invoices WHERE tax_journal_id IS NOT NULL
            UNION SELECT cogs_journal_id FROM sales_invoices WHERE cogs_journal_id IS NOT NULL
        )
        """
    )
    cur.execute(
        """
        UPDATE journal
        SET source_type='purchases',
            source_id=(SELECT id FROM purchase_invoices WHERE journal_id=journal.id OR tax_journal_id=journal.id)
        WHERE id IN (
            SELECT journal_id FROM purchase_invoices WHERE journal_id IS NOT NULL
            UNION SELECT tax_journal_id FROM purchase_invoices WHERE tax_journal_id IS NOT NULL
        )
        """
    )
    cur.execute(
        """
        UPDATE journal
        SET source_type='receipts',
            source_id=(SELECT id FROM receipt_vouchers WHERE journal_id=journal.id)
        WHERE id IN (SELECT journal_id FROM receipt_vouchers WHERE journal_id IS NOT NULL)
        """
    )
    cur.execute(
        """
        UPDATE journal
        SET source_type='payments',
            source_id=(SELECT id FROM payment_vouchers WHERE journal_id=journal.id)
        WHERE id IN (SELECT journal_id FROM payment_vouchers WHERE journal_id IS NOT NULL)
        """
    )

    cur.execute("SELECT * FROM users WHERE username='admin'")
    if not cur.fetchone():
        os.makedirs(INSTANCE_DIR, exist_ok=True)
        bootstrap_password = os.environ.get("ERP_BOOTSTRAP_ADMIN_PASSWORD", "").strip() or secrets.token_urlsafe(12)
        cur.execute(
            "INSERT INTO users(username,password,role) VALUES(?,?,?)",
            ("admin", generate_password_hash(bootstrap_password), "admin"),
        )
        with open(BOOTSTRAP_CREDENTIALS_FILE, "w", encoding="utf-8") as handle:
            handle.write("username=admin\n")
            handle.write(f"password={bootstrap_password}\n")
    else:
        cur.execute("UPDATE users SET role='admin' WHERE username='admin'")

    cur.execute("SELECT id FROM company_settings WHERE id=1")
    if not cur.fetchone():
        cur.execute(
            """
            INSERT INTO company_settings(
                id,company_name,tax_number,commercial_register,address,phone,email,default_tax_rate,invoice_footer
            )
            VALUES (1,?,?,?,?,?,?,?,?)
            """,
            (
                "شركة تجريبية للصناعات",
                "000-000-000",
                "123456",
                "القاهرة - جمهورية مصر العربية",
                "01000000000",
                "info@example.com",
                14,
                "شكراً لتعاملكم معنا",
            ),
        )

    for code, name, account_type in DEFAULT_ACCOUNTS:
        cur.execute("SELECT id FROM accounts WHERE code=?", (code,))
        if cur.fetchone():
            cur.execute(
                "UPDATE accounts SET name=?, type=? WHERE code=?",
                (name, account_type, code),
            )
        else:
            cur.execute(
                "INSERT INTO accounts(code,name,type) VALUES (?,?,?)",
                (code, name, account_type),
            )

    for role, permissions in DEFAULT_ROLE_PERMISSIONS.items():
        for permission_key, access_level in permissions.items():
            cur.execute(
                """
                INSERT OR IGNORE INTO role_permissions(role,permission_key,access_level)
                VALUES (?,?,?)
                """,
                (role, permission_key, access_level),
            )

    conn.commit()
    conn.close()
