"""
System health helper for the Flask ERP app.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime


REQUIRED_TABLES = [
    "accounts", "company_settings", "users", "role_permissions",
    "customers", "suppliers", "products", "journal", "ledger",
    "sales_invoices", "purchase_invoices", "receipt_vouchers", "payment_vouchers",
    "posting_control", "document_sequences", "schema_migrations",
]


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def _safe_count(cur: sqlite3.Cursor, table: str) -> int | None:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return int(cur.fetchone()[0])
    except sqlite3.Error:
        return None


def _table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def build_system_health(db_path: str, app, get_migration_status_func) -> dict:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    checks = []
    stats = {}

    def add_check(name: str, ok: bool, details: str = "", level: str = "success") -> None:
        checks.append({
            "name": name,
            "ok": ok,
            "details": details,
            "level": level if ok else "danger",
        })

    db_exists = os.path.exists(db_path)
    add_check("Database file", db_exists, db_path if db_exists else "database.db غير موجود")

    if db_exists:
        try:
            size_mb = os.path.getsize(db_path) / (1024 * 1024)
            stats["db_size_mb"] = round(size_mb, 2)
            conn = _connect(db_path)
            cur = conn.cursor()

            cur.execute("PRAGMA integrity_check")
            integrity = cur.fetchone()[0]
            add_check("SQLite integrity", integrity == "ok", integrity)

            missing = [t for t in REQUIRED_TABLES if not _table_exists(cur, t)]
            add_check(
                "Required tables",
                not missing,
                "كل الجداول الأساسية موجودة" if not missing else "ناقص: " + ", ".join(missing),
            )

            stats["users"] = _safe_count(cur, "users") or 0
            stats["accounts"] = _safe_count(cur, "accounts") or 0
            stats["customers"] = _safe_count(cur, "customers") or 0
            stats["suppliers"] = _safe_count(cur, "suppliers") or 0
            stats["products"] = _safe_count(cur, "products") or 0
            stats["journal_rows"] = _safe_count(cur, "journal") or 0

            try:
                cur.execute("SELECT COUNT(*) FROM journal WHERE status='posted'")
                stats["posted_journals"] = int(cur.fetchone()[0])
            except sqlite3.Error:
                stats["posted_journals"] = 0

            try:
                cur.execute("SELECT COUNT(*) FROM journal WHERE status='draft'")
                stats["draft_journals"] = int(cur.fetchone()[0])
            except sqlite3.Error:
                stats["draft_journals"] = 0

            try:
                migration_status = get_migration_status_func(db_path)
                add_check(
                    "Migration version",
                    migration_status["pending"] == 0,
                    f"Current {migration_status['current_version']} / Latest {migration_status['latest_version']}",
                    "success" if migration_status["pending"] == 0 else "warning",
                )
            except Exception as exc:
                migration_status = {"rows": [], "pending": "?", "current_version": "?", "latest_version": "?"}
                add_check("Migration version", False, str(exc))

            conn.close()
        except Exception as exc:
            migration_status = {"rows": [], "pending": "?", "current_version": "?", "latest_version": "?"}
            add_check("Database connection", False, str(exc))
    else:
        migration_status = {"rows": [], "pending": "?", "current_version": "?", "latest_version": "?"}

    routes = sorted(str(rule) for rule in app.url_map.iter_rules())
    stats["routes"] = len(routes)
    important_routes = ["/dashboard", "/login", "/sales", "/purchases", "/system-health"]
    missing_routes = [r for r in important_routes if r not in routes]
    add_check(
        "Important routes",
        not missing_routes,
        "Routes الأساسية موجودة" if not missing_routes else "ناقص: " + ", ".join(missing_routes),
    )

    overall_ok = all(item["ok"] for item in checks)
    return {
        "generated_at": now,
        "overall_ok": overall_ok,
        "overall_label": "Healthy" if overall_ok else "Needs attention",
        "checks": checks,
        "stats": stats,
        "migration_status": migration_status,
        "routes": routes[:250],
    }
