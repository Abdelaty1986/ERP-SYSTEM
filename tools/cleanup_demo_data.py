import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"
BACKUP_DIR = BASE_DIR / "backups"


TABLES_TO_CLEAR = [
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
]


def create_backup():
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"cleanup_before_{stamp}.db"
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def cleanup_demo_data():
    backup_path = create_backup()
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = OFF")
    cur.execute("PRAGMA busy_timeout = 30000")

    summary = []
    for table in TABLES_TO_CLEAR:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count_before = cur.fetchone()[0]
        cur.execute(f"DELETE FROM {table}")
        summary.append((table, count_before))

    cur.execute(
        "DELETE FROM sqlite_sequence WHERE name IN ({})".format(",".join(["?"] * len(TABLES_TO_CLEAR))),
        TABLES_TO_CLEAR,
    )

    cur.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    conn.close()
    return backup_path, summary


if __name__ == "__main__":
    backup_path, summary = cleanup_demo_data()
    print(f"Backup created: {backup_path}")
    for table, count_before in summary:
        print(f"{table}: cleared {count_before}")
