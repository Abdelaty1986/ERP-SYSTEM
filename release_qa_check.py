from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import app as app_module


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"
REPORT_PATH = BASE_DIR / "QA_STATUS_REPORT.md"

APP = app_module.app


ROUTES = [
    "/dashboard",
    "/settings/company",
    "/customers",
    "/suppliers",
    "/products",
    "/sales-orders",
    "/sales-deliveries",
    "/sales",
    "/sales/from-delivery",
    "/sales/financial",
    "/purchase-orders",
    "/purchase-receipts",
    "/purchases/from-receipt",
    "/purchases",
    "/receipts",
    "/payments",
    "/journal",
    "/trial-balance",
    "/reports/customers",
    "/reports/suppliers",
    "/reports/inventory",
    "/reports/customers/aging",
    "/reports/suppliers/aging",
    "/sales/1/print",
    "/purchases/1/print",
    "/purchase-orders/1/print",
    "/receipts/1/print",
    "/payments/1/print",
]


def get_demo_summary() -> dict[str, object]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    counts = {}
    for table in [
        "accounts",
        "customers",
        "suppliers",
        "products",
        "sales_orders",
        "sales_delivery_notes",
        "sales_invoices",
        "financial_sales_invoices",
        "purchase_orders",
        "purchase_receipts",
        "purchase_invoices",
        "receipt_vouchers",
        "payment_vouchers",
        "journal",
        "ledger",
    ]:
        counts[table] = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    debit, credit = cur.execute(
        "SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) FROM ledger"
    ).fetchone()
    conn.close()
    counts["trial_debit"] = float(debit or 0)
    counts["trial_credit"] = float(credit or 0)
    counts["trial_balanced"] = round(float(debit or 0) - float(credit or 0), 2) == 0
    return counts


def run_smoke_test() -> list[tuple[str, int]]:
    results: list[tuple[str, int]] = []
    with APP.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "admin"
            session["role"] = "admin"
        for route in ROUTES:
            response = client.get(route)
            results.append((route, response.status_code))
    return results


def build_report(results: list[tuple[str, int]], summary: dict[str, object]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# QA Status Report",
        "",
        f"- Generated at: `{now}`",
        f"- Accounts: `{summary['accounts']}`",
        f"- Customers: `{summary['customers']}`",
        f"- Suppliers: `{summary['suppliers']}`",
        f"- Products: `{summary['products']}`",
        f"- Journal entries: `{summary['journal']}`",
        f"- Ledger lines: `{summary['ledger']}`",
        f"- Trial debit: `{summary['trial_debit']:.2f}`",
        f"- Trial credit: `{summary['trial_credit']:.2f}`",
        f"- Trial balanced: `{'yes' if summary['trial_balanced'] else 'no'}`",
        "",
        "## Smoke Test",
        "",
        "| Route | Status |",
        "|---|---:|",
    ]
    for route, status in results:
        lines.append(f"| `{route}` | `{status}` |")
    return "\n".join(lines) + "\n"


def main() -> int:
    summary = get_demo_summary()
    results = run_smoke_test()
    report = build_report(results, summary)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)
    if any(status >= 400 for _, status in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
