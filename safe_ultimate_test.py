import argparse
import json
import os
import shutil
import sqlite3
import sys
import traceback
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ORIGINAL_DB = BASE_DIR / "database.db"
TEMP_DB = BASE_DIR / "database_ultimate_test_temp.db"

READ_ONLY_ENDPOINTS = [
    "/",
    "/landing",
    "/login",
    "/dashboard",
    "/system-health",
    "/dev-control",
    "/accounts",
    "/journal",
    "/trial-balance",
    "/customers",
    "/suppliers",
    "/products",
    "/sales",
    "/purchases",
    "/receipts",
    "/payments",
    "/inventory",
    "/reports/customers",
    "/reports/suppliers",
    "/employees",
    "/e-invoices",
]

REQUIRED_TABLES = [
    "accounts",
    "company_settings",
    "customers",
    "suppliers",
    "products",
    "journal",
    "ledger",
    "users",
]


def line(title=""):
    print("=" * 60)
    if title:
        print(title)
        print("=" * 60)


def db_fingerprint(path: Path):
    if not path.exists():
        return None
    stat = path.stat()
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def assert_safe_db(db_path: Path):
    if db_path.resolve() == ORIGINAL_DB.resolve():
        raise RuntimeError("Unsafe test blocked: test database points to the original database.db")


def copy_database():
    if not ORIGINAL_DB.exists():
        raise FileNotFoundError(f"Original database not found: {ORIGINAL_DB}")
    if TEMP_DB.exists():
        TEMP_DB.unlink()
    shutil.copy2(ORIGINAL_DB, TEMP_DB)
    assert_safe_db(TEMP_DB)
    return TEMP_DB


def cleanup_temp_database():
    try:
        if TEMP_DB.exists():
            TEMP_DB.unlink()
    except Exception as exc:
        print(f"Warning: could not delete temp database: {exc}")


def check_tables(db_path: Path):
    results = []
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing = {row[0] for row in cur.fetchall()}
        for table in REQUIRED_TABLES:
            if table in existing:
                results.append(("OK", f"table exists: {table}"))
            else:
                results.append(("ERROR", f"missing table: {table}"))
    finally:
        conn.close()
    return results


def run_temp_write_check(db_path: Path):
    assert_safe_db(db_path)
    tag = "SAFE_ULTIMATE_TEST_" + datetime.now().strftime("%Y%m%d%H%M%S")
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS safe_ultimate_test_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            "INSERT INTO safe_ultimate_test_log(tag, created_at) VALUES (?, ?)",
            (tag, datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM safe_ultimate_test_log WHERE tag=?", (tag,))
        count = cur.fetchone()[0]
        return [("OK", "write check passed on TEMP database only")] if count == 1 else [("ERROR", "write check failed on TEMP database")]
    finally:
        conn.close()


def import_flask_app(db_path: Path):
    assert_safe_db(db_path)
    os.environ["ERP_DB_PATH"] = str(db_path)
    os.environ.setdefault("SECRET_KEY", "safe-ultimate-test-secret")
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    import app as app_module
    return app_module.app


def login_test_session(client):
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = 1
        sess["username"] = "safe_test_admin"
        sess["role"] = "admin"


def route_exists(flask_app, path):
    adapter = flask_app.url_map.bind("localhost")
    try:
        adapter.match(path, method="GET")
        return True
    except Exception:
        return False


def run_page_smoke_test(flask_app):
    results = []
    client = flask_app.test_client()
    login_test_session(client)

    for path in READ_ONLY_ENDPOINTS:
        if not route_exists(flask_app, path):
            results.append(("WARNING", f"skipped missing route: {path}"))
            continue
        try:
            response = client.get(path, follow_redirects=False)
            if response.status_code < 500:
                results.append(("OK", f"GET {path} -> {response.status_code}"))
            else:
                results.append(("ERROR", f"GET {path} -> {response.status_code}"))
        except Exception as exc:
            results.append(("ERROR", f"GET {path} raised {type(exc).__name__}: {exc}"))
    return results


def print_report(mode, results, before_fp, after_fp):
    errors = [message for status, message in results if status == "ERROR"]
    warnings = [message for status, message in results if status == "WARNING"]
    passed = [message for status, message in results if status == "OK"]

    line("SAFE ULTIMATE TEST REPORT")
    print(f"MODE: {mode}")
    print(f"ORIGINAL_DB: {ORIGINAL_DB}")
    print(f"TEMP_DB: {TEMP_DB if mode == 'FULL_SAFE' else 'Not used'}")
    print(f"PASSED: {len(passed)}")
    print(f"WARNINGS: {len(warnings)}")
    print(f"ERRORS: {len(errors)}")
    print()

    print("Passed:")
    for item in passed:
        print(f"- {item}")

    print("Warnings:")
    for item in warnings:
        print(f"- {item}")

    print("Errors:")
    for item in errors:
        print(f"- {item}")

    print()
    if before_fp == after_fp:
        print("Original database unchanged: YES")
    else:
        print("Original database unchanged: NO")
        errors.append("original database fingerprint changed")

    line("FINAL RESULT")
    if errors:
        print("FAILED ❌")
    else:
        print("PASSED ✅")

    summary = {
        "mode": mode,
        "passed": len(passed),
        "warnings": warnings,
        "errors": errors,
        "original_database_unchanged": before_fp == after_fp,
    }
    print("JSON_SUMMARY:", json.dumps(summary, ensure_ascii=False))
    return 1 if errors else 0


def main():
    parser = argparse.ArgumentParser(description="Safe Ultimate Test for LedgerX Flask app")
    parser.add_argument("--mode", choices=["READ_ONLY", "FULL_SAFE"], default="READ_ONLY")
    args = parser.parse_args()

    if not ORIGINAL_DB.exists():
        print(f"❌ database.db not found at: {ORIGINAL_DB}")
        return 1

    before_fp = db_fingerprint(ORIGINAL_DB)
    results = []

    try:
        if args.mode == "READ_ONLY":
            results.extend(check_tables(ORIGINAL_DB))
        else:
            temp_db = copy_database()
            results.extend(check_tables(temp_db))
            results.extend(run_temp_write_check(temp_db))
            try:
                flask_app = import_flask_app(temp_db)
                results.extend(run_page_smoke_test(flask_app))
            except Exception as exc:
                results.append(("ERROR", f"Flask app smoke test failed: {type(exc).__name__}: {exc}"))
                traceback.print_exc()
    except Exception as exc:
        results.append(("ERROR", f"Safe Ultimate Test crashed: {type(exc).__name__}: {exc}"))
        traceback.print_exc()
    finally:
        if args.mode == "FULL_SAFE":
            cleanup_temp_database()

    after_fp = db_fingerprint(ORIGINAL_DB)
    return print_report(args.mode, results, before_fp, after_fp)


if __name__ == "__main__":
    raise SystemExit(main())
