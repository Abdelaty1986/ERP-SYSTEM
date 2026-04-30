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
LATEST_SCHEMA_VERSION = 6


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


MIGRATIONS: list[tuple[int, str, Callable[[sqlite3.Cursor], None]]] = [
    (1, "core metadata tables", migration_001_core_tables),
    (2, "permissions safety", migration_002_permissions_safety),
    (3, "posting control", migration_003_posting_control),
    (4, "document sequences", migration_004_document_sequences),
    (5, "optional columns", migration_005_optional_columns),
    (6, "performance indexes", migration_006_indexes),
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
