"""
Professional non-destructive migration system for the Ledger X / ERP Flask app.

Usage:
    from migrations import run_migrations
    run_migrations(DB_PATH)

CLI:
    python migrations.py
    python migrations.py /path/to/database.db

Important:
- This file never drops user tables.
- This file creates a timestamped backup before applying pending migrations.
- Each migration runs inside a transaction.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime
from typing import Callable, Iterable

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "database.db")
BACKUP_DIR = os.path.join(BASE_DIR, "backups", "migrations")
LATEST_SCHEMA_VERSION = 11


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def table_exists(cur: sqlite3.Cursor, table_name: str) -> bool:
    cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cur.fetchone() is not None


def column_exists(cur: sqlite3.Cursor, table_name: str, column_name: str) -> bool:
    if not table_exists(cur, table_name):
        return False
    cur.execute(f"PRAGMA table_info({table_name})")
    return any(row[1] == column_name for row in cur.fetchall())


def index_exists(cur: sqlite3.Cursor, index_name: str) -> bool:
    cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
        (index_name,),
    )
    return cur.fetchone() is not None


def add_column_if_missing(cur: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
    if table_exists(cur, table) and not column_exists(cur, table, column):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def create_index_if_missing(cur: sqlite3.Cursor, index_name: str, table: str, columns: str) -> None:
    if table_exists(cur, table) and not index_exists(cur, index_name):
        cur.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({columns})")


def ensure_migration_tables(cur: sqlite3.Cursor) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'success',
            error_message TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS db_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def get_current_version(cur: sqlite3.Cursor) -> int:
    ensure_migration_tables(cur)
    cur.execute("SELECT MAX(version) FROM schema_migrations WHERE status='success'")
    row = cur.fetchone()
    return int(row[0] or 0)


def set_meta(cur: sqlite3.Cursor, key: str, value: str) -> None:
    cur.execute(
        """
        INSERT INTO db_meta(key,value,updated_at)
        VALUES (?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
        """,
        (key, value),
    )


def backup_database(db_path: str) -> str | None:
    if not os.path.exists(db_path):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"database_before_migration_{stamp}.db")
    shutil.copy2(db_path, backup_path)
    return backup_path


def migration_001_core_tables(cur: sqlite3.Cursor) -> None:
    """Core metadata and audit/deployment helper tables."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS system_health_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL,
            details TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS app_deployments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deployed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            git_commit TEXT,
            status TEXT NOT NULL DEFAULT 'success',
            notes TEXT
        )
        """
    )


def migration_002_permissions_safety(cur: sqlite3.Cursor) -> None:
    """Make role permissions safer and compatible with future modules."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS role_permissions (
            role TEXT NOT NULL,
            permission_key TEXT NOT NULL,
            access_level TEXT NOT NULL DEFAULT 'none',
            PRIMARY KEY (role, permission_key)
        )
        """
    )
    roles = {
        "admin": "write",
        "accountant": "write",
        "sales": "read",
        "viewer": "read",
    }
    permission_keys = [
        "accounting", "customers", "suppliers", "inventory", "sales", "purchases",
        "receipts", "payments", "hr", "reports", "e_invoices"
    ]
    for role, default_level in roles.items():
        for key in permission_keys:
            level = "write" if role == "admin" else default_level
            if role == "sales" and key in {"sales", "customers", "receipts"}:
                level = "write"
            if role == "sales" and key not in {"sales", "customers", "receipts", "inventory", "reports"}:
                level = "none"
            cur.execute(
                """
                INSERT OR IGNORE INTO role_permissions(role, permission_key, access_level)
                VALUES (?,?,?)
                """,
                (role, key, level),
            )


def migration_003_posting_control(cur: sqlite3.Cursor) -> None:
    """Posting control table for accounting locking/unlocking."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS posting_control (
            group_key TEXT PRIMARY KEY,
            group_name TEXT NOT NULL,
            is_posted INTEGER NOT NULL DEFAULT 1,
            posted_at TEXT,
            posted_by TEXT
        )
        """
    )
    groups = [
        ("manual_journal", "القيود اليومية اليدوية"),
        ("sales", "فواتير البيع"),
        ("purchases", "فواتير الموردين"),
        ("receipts", "سندات القبض"),
        ("payments", "سندات الصرف"),
    ]
    for key, name in groups:
        cur.execute(
            """
            INSERT OR IGNORE INTO posting_control(group_key, group_name, is_posted, posted_at, posted_by)
            VALUES (?,?,1,CURRENT_TIMESTAMP,'migration')
            """,
            (key, name),
        )


def migration_004_document_sequences(cur: sqlite3.Cursor) -> None:
    """Document numbering sequences."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS document_sequences (
            doc_type TEXT PRIMARY KEY,
            prefix TEXT NOT NULL,
            next_number INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    defaults = [
        ("sales", "SAL", 1),
        ("purchases", "PUR", 1),
        ("sales_delivery_notes", "SDN", 1),
        ("financial_sales", "FSI", 1),
        ("purchase_receipts", "PRC", 1),
        ("sales_credit_notes", "SCN", 1),
        ("supplier_debit_notes", "SDN", 1),
        ("customer_adjustments", "CAD", 1),
    ]
    for row in defaults:
        cur.execute(
            "INSERT OR IGNORE INTO document_sequences(doc_type,prefix,next_number) VALUES (?,?,?)",
            row,
        )


def migration_005_optional_columns(cur: sqlite3.Cursor) -> None:
    """Add optional columns used by newer screens without touching existing data."""
    add_column_if_missing(cur, "journal", "source_type", "TEXT DEFAULT 'manual'")
    add_column_if_missing(cur, "journal", "source_id", "INTEGER")
    add_column_if_missing(cur, "journal", "status", "TEXT DEFAULT 'posted'")
    add_column_if_missing(cur, "sales_invoices", "status", "TEXT DEFAULT 'draft'")
    add_column_if_missing(cur, "sales_invoices", "journal_id", "INTEGER")
    add_column_if_missing(cur, "sales_invoices", "tax_journal_id", "INTEGER")
    add_column_if_missing(cur, "sales_invoices", "withholding_journal_id", "INTEGER")
    add_column_if_missing(cur, "sales_invoices", "cogs_journal_id", "INTEGER")
    add_column_if_missing(cur, "purchase_invoices", "status", "TEXT DEFAULT 'draft'")
    add_column_if_missing(cur, "purchase_invoices", "journal_id", "INTEGER")
    add_column_if_missing(cur, "purchase_invoices", "tax_journal_id", "INTEGER")
    add_column_if_missing(cur, "purchase_invoices", "withholding_journal_id", "INTEGER")
    add_column_if_missing(cur, "products", "barcode", "TEXT")
    add_column_if_missing(cur, "products", "category_id", "INTEGER")
    add_column_if_missing(cur, "users", "is_active", "INTEGER NOT NULL DEFAULT 1")


def migration_006_indexes(cur: sqlite3.Cursor) -> None:
    """Performance indexes for the most used reports and statements."""
    create_index_if_missing(cur, "idx_journal_date", "journal", "date")
    create_index_if_missing(cur, "idx_journal_source", "journal", "source_type, source_id")
    create_index_if_missing(cur, "idx_ledger_account", "ledger", "account_id")
    create_index_if_missing(cur, "idx_sales_customer_status", "sales_invoices", "customer_id, status")
    create_index_if_missing(cur, "idx_purchase_supplier_status", "purchase_invoices", "supplier_id, status")
    create_index_if_missing(cur, "idx_inventory_product", "inventory_movements", "product_id")
    create_index_if_missing(cur, "idx_receipts_customer_status", "receipt_vouchers", "customer_id, status")
    create_index_if_missing(cur, "idx_payments_supplier_status", "payment_vouchers", "supplier_id, status")


def migration_007_hr_payroll_hardening(cur: sqlite3.Cursor) -> None:
    """HR and payroll safety schema for employee codes, departments, and posting controls."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    add_column_if_missing(cur, "employees", "employee_code", "TEXT")
    add_column_if_missing(cur, "employees", "department_id", "INTEGER")
    add_column_if_missing(cur, "employees", "is_active", "INTEGER NOT NULL DEFAULT 1")

    add_column_if_missing(cur, "payroll_runs", "posting_status", "TEXT NOT NULL DEFAULT 'unposted'")
    add_column_if_missing(cur, "payroll_runs", "payment_method", "TEXT NOT NULL DEFAULT 'accrued'")
    add_column_if_missing(cur, "payroll_runs", "allowances_journal_id", "INTEGER")
    add_column_if_missing(cur, "payroll_runs", "deductions_journal_id", "INTEGER")
    add_column_if_missing(cur, "payroll_runs", "payment_journal_id", "INTEGER")
    add_column_if_missing(cur, "payroll_runs", "posted_at", "TEXT")
    add_column_if_missing(cur, "payroll_runs", "posted_by", "TEXT")

    add_column_if_missing(cur, "payroll_lines", "benefits", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "payroll_lines", "incentives", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "payroll_lines", "overtime", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "payroll_lines", "advances", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "payroll_lines", "penalties", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "payroll_lines", "absence_deduction", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "payroll_lines", "tardiness_deduction", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "payroll_lines", "total_deductions", "REAL NOT NULL DEFAULT 0")
    add_column_if_missing(cur, "payroll_lines", "posting_status", "TEXT NOT NULL DEFAULT 'unposted'")

    create_index_if_missing(cur, "idx_departments_name", "departments", "name")
    create_index_if_missing(cur, "idx_employees_department_id", "employees", "department_id")
    create_index_if_missing(cur, "idx_employees_is_active", "employees", "is_active, status")
    create_index_if_missing(cur, "idx_payroll_runs_period", "payroll_runs", "period")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_employees_employee_code ON employees(employee_code)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_payroll_lines_run_employee ON payroll_lines(run_id, employee_id)")

    for department_name in [
        "الإدارة", "الحسابات", "المبيعات", "المشتريات", "المخازن", "الموارد البشرية",
        "تكنولوجيا المعلومات", "خدمة العملاء", "التشغيل", "الصيانة", "التسويق",
        "الشئون القانونية", "الأمن", "النظافة",
    ]:
        cur.execute("INSERT OR IGNORE INTO departments(name) VALUES (?)", (department_name,))


def migration_008_enterprise_hr_blueprint(cur: sqlite3.Cursor) -> None:
    """Enterprise HR blueprint tables and payroll posting metadata."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hr_departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hr_employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT UNIQUE,
            full_name TEXT NOT NULL,
            national_id TEXT,
            phone TEXT,
            email TEXT,
            department_id INTEGER,
            job_title TEXT,
            hire_date TEXT,
            base_salary REAL DEFAULT 0,
            work_start TEXT DEFAULT '09:00',
            work_end TEXT DEFAULT '17:00',
            annual_leave_balance REAL DEFAULT 21,
            status TEXT DEFAULT 'active',
            is_active INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hr_payroll_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payroll_month TEXT NOT NULL UNIQUE,
            run_date TEXT NOT NULL,
            status TEXT DEFAULT 'draft',
            posting_status TEXT DEFAULT 'unposted',
            payment_method TEXT DEFAULT 'accrued',
            total_gross REAL DEFAULT 0,
            total_deductions REAL DEFAULT 0,
            total_net REAL DEFAULT 0,
            journal_id INTEGER,
            payment_journal_id INTEGER,
            notes TEXT,
            posted_at TEXT,
            posted_by TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hr_payroll_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            base_salary REAL DEFAULT 0,
            allowance_amount REAL DEFAULT 0,
            bonus_amount REAL DEFAULT 0,
            incentive_amount REAL DEFAULT 0,
            overtime_amount REAL DEFAULT 0,
            insurance_amount REAL DEFAULT 0,
            tax_amount REAL DEFAULT 0,
            loan_amount REAL DEFAULT 0,
            penalty_amount REAL DEFAULT 0,
            late_deduction REAL DEFAULT 0,
            absence_deduction REAL DEFAULT 0,
            other_deduction REAL DEFAULT 0,
            gross_salary REAL DEFAULT 0,
            total_deductions REAL DEFAULT 0,
            net_salary REAL DEFAULT 0,
            present_days INTEGER DEFAULT 0,
            absent_days INTEGER DEFAULT 0,
            late_minutes INTEGER DEFAULT 0,
            early_minutes INTEGER DEFAULT 0,
            overtime_minutes INTEGER DEFAULT 0,
            posting_status TEXT DEFAULT 'unposted',
            journal_id INTEGER,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hr_salary_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            adjustment_month TEXT NOT NULL,
            adjustment_type TEXT NOT NULL DEFAULT 'allowance',
            title TEXT NOT NULL,
            amount REAL DEFAULT 0,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hr_payroll_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            late_deduction_per_min REAL DEFAULT 0,
            absent_day_deduction_rate REAL DEFAULT 1,
            overtime_rate_per_hour REAL DEFAULT 0,
            salary_expense_account_code TEXT DEFAULT '5110',
            variable_compensation_account_code TEXT DEFAULT '5115',
            salary_payable_account_code TEXT DEFAULT '2310',
            insurance_payable_account_code TEXT DEFAULT '2220',
            tax_payable_account_code TEXT DEFAULT '2340',
            deductions_payable_account_code TEXT DEFAULT '2330',
            cash_account_code TEXT DEFAULT '1100',
            bank_account_code TEXT DEFAULT '1200',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    add_column_if_missing(cur, "hr_employees", "employee_code", "TEXT")
    add_column_if_missing(cur, "hr_employees", "national_id", "TEXT")
    add_column_if_missing(cur, "hr_employees", "phone", "TEXT")
    add_column_if_missing(cur, "hr_employees", "email", "TEXT")
    add_column_if_missing(cur, "hr_employees", "department_id", "INTEGER")
    add_column_if_missing(cur, "hr_employees", "job_title", "TEXT")
    add_column_if_missing(cur, "hr_employees", "hire_date", "TEXT")
    add_column_if_missing(cur, "hr_employees", "base_salary", "REAL DEFAULT 0")
    add_column_if_missing(cur, "hr_employees", "status", "TEXT DEFAULT 'active'")
    add_column_if_missing(cur, "hr_employees", "is_active", "INTEGER NOT NULL DEFAULT 1")
    add_column_if_missing(cur, "hr_payroll_runs", "posting_status", "TEXT DEFAULT 'unposted'")
    add_column_if_missing(cur, "hr_payroll_runs", "payment_method", "TEXT DEFAULT 'accrued'")
    add_column_if_missing(cur, "hr_payroll_runs", "posted_at", "TEXT")
    add_column_if_missing(cur, "hr_payroll_runs", "posted_by", "TEXT")
    add_column_if_missing(cur, "hr_payroll_runs", "journal_id", "INTEGER")
    add_column_if_missing(cur, "hr_payroll_runs", "payment_journal_id", "INTEGER")
    add_column_if_missing(cur, "hr_payroll_runs", "notes", "TEXT")
    add_column_if_missing(cur, "hr_payroll_runs", "created_by", "TEXT")
    for column in [
        ("allowance_amount", "REAL DEFAULT 0"),
        ("bonus_amount", "REAL DEFAULT 0"),
        ("incentive_amount", "REAL DEFAULT 0"),
        ("overtime_amount", "REAL DEFAULT 0"),
        ("insurance_amount", "REAL DEFAULT 0"),
        ("tax_amount", "REAL DEFAULT 0"),
        ("loan_amount", "REAL DEFAULT 0"),
        ("penalty_amount", "REAL DEFAULT 0"),
        ("late_deduction", "REAL DEFAULT 0"),
        ("absence_deduction", "REAL DEFAULT 0"),
        ("other_deduction", "REAL DEFAULT 0"),
        ("gross_salary", "REAL DEFAULT 0"),
        ("total_deductions", "REAL DEFAULT 0"),
        ("net_salary", "REAL DEFAULT 0"),
        ("posting_status", "TEXT DEFAULT 'unposted'"),
        ("journal_id", "INTEGER"),
        ("created_at", "TEXT"),
    ]:
        add_column_if_missing(cur, "hr_payroll_lines", column[0], column[1])
    create_index_if_missing(cur, "idx_hr_departments_name", "hr_departments", "name")
    create_index_if_missing(cur, "idx_hr_employees_active", "hr_employees", "is_active, status")
    create_index_if_missing(cur, "idx_hr_employees_department", "hr_employees", "department_id")
    create_index_if_missing(cur, "idx_hr_payroll_runs_month", "hr_payroll_runs", "payroll_month")
    create_index_if_missing(cur, "idx_hr_payroll_lines_run_employee", "hr_payroll_lines", "run_id, employee_id")
    create_index_if_missing(cur, "idx_hr_salary_adjustments_employee_month", "hr_salary_adjustments", "employee_id, adjustment_month")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_hr_employees_employee_code ON hr_employees(employee_code)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_hr_payroll_lines_run_employee ON hr_payroll_lines(run_id, employee_id)")
    for department_name in [
        "الإدارة", "الحسابات", "المبيعات", "المشتريات", "المخازن", "الموارد البشرية",
        "تكنولوجيا المعلومات", "خدمة العملاء", "التشغيل", "الصيانة", "التسويق",
        "الشئون القانونية", "الأمن", "النظافة",
    ]:
        cur.execute("INSERT OR IGNORE INTO hr_departments(name) VALUES (?)", (department_name,))


def migration_009_measurement_units(cur: sqlite3.Cursor) -> None:
    """Inventory measurement units, product conversions, and invoice line unit metadata."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS measurement_units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            code TEXT UNIQUE,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS product_units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            unit_id INTEGER NOT NULL,
            conversion_factor REAL NOT NULL DEFAULT 1,
            purchase_price REAL DEFAULT 0,
            sale_price REAL DEFAULT 0,
            barcode TEXT,
            is_default_purchase INTEGER DEFAULT 0,
            is_default_sale INTEGER DEFAULT 0,
            is_base_unit INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(product_id) REFERENCES products(id),
            FOREIGN KEY(unit_id) REFERENCES measurement_units(id)
        )
        """
    )
    for table_name in ("sales_invoice_lines", "purchase_invoice_lines"):
        add_column_if_missing(cur, table_name, "unit_id", "INTEGER")
        add_column_if_missing(cur, table_name, "unit_name", "TEXT")
        add_column_if_missing(cur, table_name, "conversion_factor", "REAL NOT NULL DEFAULT 1")
        add_column_if_missing(cur, table_name, "quantity_base", "REAL")

    create_index_if_missing(cur, "idx_measurement_units_name", "measurement_units", "name")
    create_index_if_missing(cur, "idx_measurement_units_code", "measurement_units", "code")
    create_index_if_missing(cur, "idx_product_units_product", "product_units", "product_id")
    create_index_if_missing(cur, "idx_product_units_unit", "product_units", "unit_id")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_product_units_product_unit ON product_units(product_id, unit_id)")

    defaults = [
        ("قطعة", "PCS", "الوحدة الأساسية العامة للأصناف الفردية"),
        ("وحدة", "UNIT", "وحدة عامة للاستخدام الافتراضي"),
        ("علبة", "BOX", "وحدة تعبئة متوسطة"),
        ("كرتونة", "CTN", "وحدة تعبئة كبيرة"),
        ("كجم", "KG", "وحدة وزن"),
        ("جرام", "G", "وحدة وزن فرعية"),
        ("لتر", "LTR", "وحدة حجم"),
        ("متر", "M", "وحدة طول"),
    ]
    for row in defaults:
        cur.execute(
            """
            INSERT OR IGNORE INTO measurement_units(name, code, description, is_active)
            VALUES (?,?,?,1)
            """,
            row,
        )

    cur.execute("SELECT id FROM measurement_units WHERE name='وحدة'")
    default_unit = cur.fetchone()
    if default_unit:
        default_unit_id = default_unit[0]
        cur.execute(
            """
            INSERT OR IGNORE INTO product_units(
                product_id, unit_id, conversion_factor, purchase_price, sale_price,
                is_default_purchase, is_default_sale, is_base_unit, is_active
            )
            SELECT p.id, ?, 1, COALESCE(p.purchase_price, 0), COALESCE(p.sale_price, 0), 1, 1, 1, 1
            FROM products p
            WHERE NOT EXISTS (
                SELECT 1 FROM product_units pu WHERE pu.product_id = p.id
            )
            """,
            (default_unit_id,),
        )
        for table_name in ("sales_invoice_lines", "purchase_invoice_lines"):
            cur.execute(
                f"""
                UPDATE {table_name}
                SET conversion_factor = COALESCE(NULLIF(conversion_factor, 0), 1),
                    quantity_base = COALESCE(quantity_base, quantity * COALESCE(NULLIF(conversion_factor, 0), 1)),
                    unit_name = COALESCE(unit_name, 'وحدة'),
                    unit_id = COALESCE(unit_id, ?)
                """,
                (default_unit_id,),
            )


def migration_010_order_units(cur: sqlite3.Cursor) -> None:
    """Add unit metadata to orders and their warehouse fulfillment documents."""
    for table_name in ("sales_order_lines", "purchase_order_lines", "sales_delivery_notes", "purchase_receipts"):
        add_column_if_missing(cur, table_name, "unit_id", "INTEGER")
        add_column_if_missing(cur, table_name, "unit_name", "TEXT")
        add_column_if_missing(cur, table_name, "conversion_factor", "REAL NOT NULL DEFAULT 1")
        add_column_if_missing(cur, table_name, "quantity_base", "REAL")

    cur.execute("SELECT id FROM measurement_units WHERE name='وحدة'")
    default_unit_row = cur.fetchone()
    default_unit_id = default_unit_row[0] if default_unit_row else None

    if default_unit_id:
        for table_name, quantity_column in (
            ("sales_order_lines", "quantity"),
            ("purchase_order_lines", "quantity"),
            ("sales_delivery_notes", "delivered_quantity"),
            ("purchase_receipts", "received_quantity"),
        ):
            cur.execute(
                f"""
                UPDATE {table_name}
                SET conversion_factor = COALESCE(NULLIF(conversion_factor, 0), 1),
                    quantity_base = COALESCE(quantity_base, {quantity_column} * COALESCE(NULLIF(conversion_factor, 0), 1)),
                    unit_name = COALESCE(unit_name, 'وحدة'),
                    unit_id = COALESCE(unit_id, ?)
                """,
                (default_unit_id,),
            )

    cur.execute(
        """
        UPDATE sales_delivery_notes
        SET unit_id = COALESCE(unit_id, (
                SELECT sol.unit_id
                FROM sales_order_lines sol
                WHERE sol.id = sales_delivery_notes.sales_order_line_id
            )),
            unit_name = COALESCE(unit_name, (
                SELECT sol.unit_name
                FROM sales_order_lines sol
                WHERE sol.id = sales_delivery_notes.sales_order_line_id
            )),
            conversion_factor = COALESCE(NULLIF(conversion_factor, 0), (
                SELECT COALESCE(NULLIF(sol.conversion_factor, 0), 1)
                FROM sales_order_lines sol
                WHERE sol.id = sales_delivery_notes.sales_order_line_id
            ), 1),
            quantity_base = COALESCE(quantity_base, delivered_quantity * COALESCE((
                SELECT COALESCE(NULLIF(sol.conversion_factor, 0), 1)
                FROM sales_order_lines sol
                WHERE sol.id = sales_delivery_notes.sales_order_line_id
            ), COALESCE(NULLIF(conversion_factor, 0), 1), 1))
        """
    )
    cur.execute(
        """
        UPDATE purchase_receipts
        SET unit_id = COALESCE(unit_id, (
                SELECT pol.unit_id
                FROM purchase_order_lines pol
                WHERE pol.id = purchase_receipts.purchase_order_line_id
            )),
            unit_name = COALESCE(unit_name, (
                SELECT pol.unit_name
                FROM purchase_order_lines pol
                WHERE pol.id = purchase_receipts.purchase_order_line_id
            )),
            conversion_factor = COALESCE(NULLIF(conversion_factor, 0), (
                SELECT COALESCE(NULLIF(pol.conversion_factor, 0), 1)
                FROM purchase_order_lines pol
                WHERE pol.id = purchase_receipts.purchase_order_line_id
            ), 1),
            quantity_base = COALESCE(quantity_base, received_quantity * COALESCE((
                SELECT COALESCE(NULLIF(pol.conversion_factor, 0), 1)
                FROM purchase_order_lines pol
                WHERE pol.id = purchase_receipts.purchase_order_line_id
            ), COALESCE(NULLIF(conversion_factor, 0), 1), 1))
        """
    )


def migration_011_invoice_schema_fixes(cur: sqlite3.Cursor) -> None:
    """Fix invoice line totals, VAT fields, tax identifiers, and unit metadata safely."""
    for table_name in ("sales_invoice_lines", "purchase_invoice_lines"):
        add_column_if_missing(cur, table_name, "grand_total", "REAL DEFAULT 0")
        add_column_if_missing(cur, table_name, "vat_amount", "REAL DEFAULT 0")
        add_column_if_missing(cur, table_name, "unit_id", "INTEGER")
        add_column_if_missing(cur, table_name, "unit_name", "TEXT")
        add_column_if_missing(cur, table_name, "conversion_factor", "REAL NOT NULL DEFAULT 1")
        add_column_if_missing(cur, table_name, "quantity_base", "REAL")

        if table_exists(cur, table_name):
            cur.execute(f"PRAGMA table_info({table_name})")
            cols = {row[1] for row in cur.fetchall()}

            # Normalize conversion factor safely.
            if "conversion_factor" in cols:
                cur.execute(
                    f"""
                    UPDATE {table_name}
                    SET conversion_factor = COALESCE(NULLIF(conversion_factor, 0), 1)
                    """
                )

            # Fill quantity_base only if quantity exists.
            if "quantity_base" in cols and "quantity" in cols and "conversion_factor" in cols:
                cur.execute(
                    f"""
                    UPDATE {table_name}
                    SET quantity_base = COALESCE(quantity_base, quantity * COALESCE(NULLIF(conversion_factor, 0), 1))
                    """
                )

            # Fill unit name safely.
            if "unit_name" in cols:
                cur.execute(
                    f"""
                    UPDATE {table_name}
                    SET unit_name = COALESCE(unit_name, 'وحدة')
                    """
                )

            # Fill VAT amount from whichever tax column exists.
            if "vat_amount" in cols:
                if "tax_amount" in cols:
                    cur.execute(
                        f"""
                        UPDATE {table_name}
                        SET vat_amount = COALESCE(vat_amount, tax_amount, 0)
                        """
                    )
                else:
                    cur.execute(
                        f"""
                        UPDATE {table_name}
                        SET vat_amount = COALESCE(vat_amount, 0)
                        """
                    )

            # Fill grand_total using available columns only.
            if "grand_total" in cols:
                if "total" in cols and "tax_amount" in cols:
                    cur.execute(
                        f"""
                        UPDATE {table_name}
                        SET grand_total = COALESCE(grand_total, total + COALESCE(tax_amount, 0))
                        """
                    )
                elif "total" in cols and "vat_amount" in cols:
                    cur.execute(
                        f"""
                        UPDATE {table_name}
                        SET grand_total = COALESCE(grand_total, total + COALESCE(vat_amount, 0))
                        """
                    )
                elif "total" in cols:
                    cur.execute(
                        f"""
                        UPDATE {table_name}
                        SET grand_total = COALESCE(grand_total, total)
                        """
                    )
                elif "quantity" in cols and "unit_price" in cols:
                    cur.execute(
                        f"""
                        UPDATE {table_name}
                        SET grand_total = COALESCE(grand_total, quantity * unit_price)
                        """
                    )
                else:
                    cur.execute(
                        f"""
                        UPDATE {table_name}
                        SET grand_total = COALESCE(grand_total, 0)
                        """
                    )

    add_column_if_missing(cur, "suppliers", "tax_id", "TEXT")
    add_column_if_missing(cur, "customers", "tax_id", "TEXT")
    add_column_if_missing(cur, "ledger", "vat_amount", "REAL DEFAULT 0")
    add_column_if_missing(cur, "journal", "vat_amount", "REAL DEFAULT 0")

    if table_exists(cur, "ledger"):
        cur.execute("UPDATE ledger SET vat_amount = COALESCE(vat_amount, 0)")
    if table_exists(cur, "journal"):
        cur.execute("UPDATE journal SET vat_amount = COALESCE(vat_amount, 0)")

    create_index_if_missing(cur, "idx_sales_invoice_lines_invoice", "sales_invoice_lines", "invoice_id")
    create_index_if_missing(cur, "idx_purchase_invoice_lines_invoice", "purchase_invoice_lines", "invoice_id")


MIGRATIONS: list[tuple[int, str, Callable[[sqlite3.Cursor], None]]] = [
    (1, "core metadata tables", migration_001_core_tables),
    (2, "permissions safety", migration_002_permissions_safety),
    (3, "posting control", migration_003_posting_control),
    (4, "document sequences", migration_004_document_sequences),
    (5, "optional columns", migration_005_optional_columns),
    (6, "performance indexes", migration_006_indexes),
    (7, "hr payroll hardening", migration_007_hr_payroll_hardening),
    (8, "enterprise hr blueprint", migration_008_enterprise_hr_blueprint),
    (9, "measurement units and product conversions", migration_009_measurement_units),
    (10, "order unit metadata and warehouse conversion safety", migration_010_order_units),
    (11, "invoice schema fixes for units and vat", migration_011_invoice_schema_fixes),
]


def run_migrations(db_path: str = DEFAULT_DB_PATH) -> dict:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    backup_path = backup_database(db_path)
    conn = connect(db_path)
    cur = conn.cursor()
    ensure_migration_tables(cur)
    current_version = get_current_version(cur)
    applied = []

    try:
        for version, name, func in MIGRATIONS:
            if version <= current_version:
                continue
            try:
                cur.execute("BEGIN")
                func(cur)
                cur.execute(
                    """
                    INSERT INTO schema_migrations(version,name,status,error_message)
                    VALUES (?,?, 'success', NULL)
                    """,
                    (version, name),
                )
                set_meta(cur, "schema_version", str(version))
                conn.commit()
                applied.append({"version": version, "name": name, "status": "success"})
            except Exception as exc:
                conn.rollback()
                cur.execute(
                    """
                    INSERT OR REPLACE INTO schema_migrations(version,name,status,error_message)
                    VALUES (?,?, 'failed', ?)
                    """,
                    (version, name, str(exc)),
                )
                conn.commit()
                raise

        set_meta(cur, "schema_version", str(LATEST_SCHEMA_VERSION))
        set_meta(cur, "last_migration_run", datetime.now().isoformat(timespec="seconds"))
        conn.commit()
        return {
            "ok": True,
            "db_path": db_path,
            "backup_path": backup_path,
            "current_version": LATEST_SCHEMA_VERSION,
            "applied": applied,
        }
    finally:
        conn.close()


def get_migration_status(db_path: str = DEFAULT_DB_PATH) -> dict:
    conn = connect(db_path)
    cur = conn.cursor()
    ensure_migration_tables(cur)
    current_version = get_current_version(cur)
    cur.execute(
        """
        SELECT version,name,applied_at,status,error_message
        FROM schema_migrations
        ORDER BY version DESC
        """
    )
    rows = cur.fetchall()
    conn.close()
    return {
        "latest_version": LATEST_SCHEMA_VERSION,
        "current_version": current_version,
        "pending": max(LATEST_SCHEMA_VERSION - current_version, 0),
        "rows": rows,
    }


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_PATH
    result = run_migrations(path)
    print(result)
