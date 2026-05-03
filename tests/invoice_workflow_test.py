import shutil
import sys
import tempfile
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TMP_ROOT = PROJECT_ROOT / "tests" / "tmp"
TMP_ROOT.mkdir(parents=True, exist_ok=True)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app as appmod


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def fetchone(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchone()


def find_header_row(sheet):
    for row_index in range(1, 30):
        values = [str(cell.value).strip() for cell in sheet[row_index] if cell.value is not None]
        if not values:
            continue
        joined = " | ".join(values)
        if ("كمية" in joined or "الكمية" in joined) and "سعر" in joined and "وحدة" in joined:
            return row_index, values
    return 3, [str(cell.value).strip() for cell in sheet[3] if cell.value is not None]


def main():
    source_db = PROJECT_ROOT / "database.db"
    temp_dir = Path(tempfile.mkdtemp(prefix="erp-integration-", dir=str(TMP_ROOT)))
    temp_db = temp_dir / "database_test.db"
    shutil.copy2(source_db, temp_db)

    old_db_path = appmod.DB_PATH
    old_module_db_path = appmod.MODULE_DEPS.get("DB_PATH")

    appmod.DB_PATH = str(temp_db)
    appmod.MODULE_DEPS["DB_PATH"] = str(temp_db)
    appmod.run_migrations(str(temp_db))
    appmod.init_db()
    appmod.app.config["TESTING"] = True

    client = appmod.app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = 1
        session["username"] = "codex-banks-test"
        session["role"] = "admin"

    conn = appmod.db()
    cur = conn.cursor()

    customer_name = "عميل اختبار البنوك"
    supplier_name = "مورد اختبار البنوك"
    cur.execute("INSERT INTO customers(name,tax_id) VALUES (?,?)", (customer_name, "TAX-BANK-001"))
    customer_id = cur.lastrowid
    cur.execute("INSERT INTO suppliers(name,tax_id) VALUES (?,?)", (supplier_name, "SUP-BANK-001"))
    supplier_id = cur.lastrowid
    cur.execute(
        "INSERT INTO products(code,name,unit,purchase_price,sale_price,stock_quantity) VALUES (?,?,?,?,?,?)",
        ("BANK-PROD", "صنف اختبار البنك", "علبة", 10, 20, 100),
    )
    product_id = cur.lastrowid
    conn.commit()

    treasury_gl = fetchone(cur, "SELECT id FROM accounts WHERE code='1100' LIMIT 1")
    treasury_gl = treasury_gl[0] if treasury_gl else None
    bank_gl_1 = fetchone(cur, "SELECT id FROM accounts WHERE code IN ('1200','1210','1110','1120') ORDER BY code LIMIT 1")
    bank_gl_1 = bank_gl_1[0] if bank_gl_1 else fetchone(cur, "SELECT id FROM accounts WHERE id<>? ORDER BY code LIMIT 1", (treasury_gl or 0,))[0]
    bank_gl_2 = fetchone(cur, "SELECT id FROM accounts WHERE code IN ('1210','1120','1110','1200') AND id<>? ORDER BY code LIMIT 1", (bank_gl_1,))
    bank_gl_2 = bank_gl_2[0] if bank_gl_2 else fetchone(cur, "SELECT id FROM accounts WHERE id<>? ORDER BY code LIMIT 1", (bank_gl_1,))[0]
    treasury_gl = treasury_gl or bank_gl_2
    customer_control = fetchone(cur, "SELECT id FROM accounts WHERE code='1300' LIMIT 1")[0]
    supplier_control = fetchone(cur, "SELECT id FROM accounts WHERE code='2100' LIMIT 1")[0]
    expense_gl = fetchone(cur, "SELECT id FROM accounts WHERE code IN ('5295','6100') ORDER BY code LIMIT 1")
    expense_gl = expense_gl[0] if expense_gl else supplier_control
    conn.commit()

    response = client.post(
        "/sales",
        data={
            "date": "2026-05-01",
            "invoice_number": "INV-TEST-1",
            "customer_id": str(customer_id),
            "payment_type": "credit",
            "product_id[]": [str(product_id)],
            "quantity[]": ["2"],
            "unit_price[]": ["20"],
        },
        follow_redirects=False,
    )
    assert_true(response.status_code in (302, 303), "sales invoice creation failed")

    response = client.get("/reports/vat?format=excel")
    assert_true(response.status_code == 200, "VAT report export failed")
    wb = load_workbook(BytesIO(response.data))
    sheet = wb.active
    _, headers = find_header_row(sheet)
    assert_true(any("كمية" in header for header in headers), "VAT report is missing quantity")
    assert_true(any("سعر" in header for header in headers), "VAT report is missing unit price")
    assert_true(any("وحدة" in header for header in headers), "VAT report is missing unit")
    assert_true(any("ضريبي" in header for header in headers), "VAT report is missing tax number")

    response = client.post(
        "/banks",
        data={
            "name": "البنك الأول",
            "branch": "الفرع الرئيسي",
            "account_number": "10001",
            "currency": "EGP",
            "opening_balance": "1000",
            "gl_account_id": str(bank_gl_1),
            "is_active": "1",
        },
        follow_redirects=False,
    )
    assert_true(response.status_code in (302, 303), "bank creation failed")
    response = client.post(
        "/banks",
        data={
            "name": "البنك الثاني",
            "branch": "فرع 2",
            "account_number": "20002",
            "currency": "EGP",
            "opening_balance": "500",
            "gl_account_id": str(bank_gl_2),
            "is_active": "1",
        },
        follow_redirects=False,
    )
    assert_true(response.status_code in (302, 303), "second bank creation failed")

    bank_1_id = fetchone(cur, "SELECT id FROM banks WHERE name='البنك الأول'")[0]
    bank_2_id = fetchone(cur, "SELECT id FROM banks WHERE name='البنك الثاني'")[0]

    response = client.post(
        "/banks/transactions",
        data={
            "txn_type": "deposit",
            "bank_id": str(bank_1_id),
            "txn_date": "2026-05-02",
            "doc_no": "BTX-DEP-001",
            "amount": "250",
            "description": "إيداع اختبار",
            "counterparty_account_id": str(customer_control),
        },
        follow_redirects=False,
    )
    assert_true(response.status_code in (302, 303), "bank deposit failed")

    response = client.post(
        "/banks/transactions",
        data={
            "txn_type": "withdrawal",
            "bank_id": str(bank_1_id),
            "txn_date": "2026-05-03",
            "doc_no": "BTX-WDR-001",
            "amount": "75",
            "description": "سحب اختبار",
            "counterparty_account_id": str(expense_gl),
        },
        follow_redirects=False,
    )
    assert_true(response.status_code in (302, 303), "bank withdrawal failed")

    response = client.post(
        "/banks/transfers",
        data={
            "source_bank_id": str(bank_1_id),
            "target_bank_id": str(bank_2_id),
            "txn_date": "2026-05-04",
            "doc_no": "BTR-001",
            "amount": "125",
            "description": "تحويل اختبار",
            "reference_no": "REF-TR-1",
        },
        follow_redirects=False,
    )
    assert_true(response.status_code in (302, 303), "bank transfer failed")

    response = client.post(
        "/banks/transactions",
        data={
            "txn_type": "treasury_to_bank",
            "bank_id": str(bank_1_id),
            "txn_date": "2026-05-05",
            "doc_no": "BTX-TTB-001",
            "amount": "60",
            "description": "تحويل خزينة إلى بنك",
            "counterparty_account_id": str(treasury_gl),
        },
        follow_redirects=False,
    )
    assert_true(response.status_code in (302, 303), "treasury to bank failed")

    before_duplicate = fetchone(cur, "SELECT COUNT(*) FROM bank_transactions WHERE txn_type='deposit' AND doc_no='BTX-DUP-1'")[0]
    response = client.post(
        "/banks/transactions",
        data={
            "txn_type": "deposit",
            "bank_id": str(bank_1_id),
            "txn_date": "2026-05-06",
            "doc_no": "BTX-DUP-1",
            "amount": "20",
            "description": "أول تكرار",
            "counterparty_account_id": str(customer_control),
        },
        follow_redirects=True,
    )
    assert_true(response.status_code == 200, "first duplicate-guard request failed")
    after_first = fetchone(cur, "SELECT COUNT(*) FROM bank_transactions WHERE txn_type='deposit' AND doc_no='BTX-DUP-1'")[0]
    response = client.post(
        "/banks/transactions",
        data={
            "txn_type": "deposit",
            "bank_id": str(bank_1_id),
            "txn_date": "2026-05-06",
            "doc_no": "BTX-DUP-1",
            "amount": "20",
            "description": "ثاني تكرار",
            "counterparty_account_id": str(customer_control),
        },
        follow_redirects=True,
    )
    assert_true(response.status_code == 200, "duplicate-guard followup failed")
    after_duplicate = fetchone(cur, "SELECT COUNT(*) FROM bank_transactions WHERE txn_type='deposit' AND doc_no='BTX-DUP-1'")[0]
    assert_true(after_first == before_duplicate + 1, "first deposit with duplicate test doc was not saved")
    assert_true(after_duplicate == after_first, "duplicate deposit document number was not blocked")

    response = client.get(f"/banks/statements?bank_id={bank_1_id}")
    assert_true(response.status_code == 200, "bank statement route failed")
    assert_true("BTX-DEP-001".encode("utf-8") in response.data, "bank statement does not show deposit doc")

    response = client.post(
        "/banks/reconciliation",
        data={
            "bank_id": str(bank_1_id),
            "statement_date": "2026-05-06",
            "from_date": "2026-05-01",
            "to_date": "2026-05-06",
            "doc_no": "BRC-001",
            "statement_balance": "1130",
            "lines_text": "2026-05-02|250|BTX-DEP-001|إيداع اختبار\n2026-05-03|75|BTX-WDR-001|سحب اختبار",
        },
        follow_redirects=False,
    )
    assert_true(response.status_code in (302, 303), "bank reconciliation creation failed")
    reconciliation_id = fetchone(cur, "SELECT id FROM bank_reconciliations WHERE doc_no='BRC-001'")[0]
    matched_count = fetchone(cur, "SELECT COUNT(*) FROM bank_reconciliation_lines WHERE reconciliation_id=? AND match_status='matched'", (reconciliation_id,))[0]
    assert_true(matched_count >= 2, "bank reconciliation did not match expected movements")

    response = client.post(
        "/banks/checks/receivable",
        data={
            "doc_no": "RCH-001",
            "check_number": "CHK-R-1",
            "bank_id": str(bank_1_id),
            "customer_id": str(customer_id),
            "due_date": "2026-05-10",
            "amount": "90",
        },
        follow_redirects=False,
    )
    assert_true(response.status_code in (302, 303), "receivable check creation failed")
    receivable_check_id = fetchone(cur, "SELECT id FROM receivable_checks WHERE check_number='CHK-R-1'")[0]
    response = client.post(
        f"/banks/checks/receivable/{receivable_check_id}/action",
        data={"action": "deposit"},
        follow_redirects=False,
    )
    assert_true(response.status_code in (302, 303), "receivable check deposit failed")
    response = client.post(
        f"/banks/checks/receivable/{receivable_check_id}/action",
        data={"action": "bounce"},
        follow_redirects=False,
    )
    assert_true(response.status_code in (302, 303), "receivable check bounce failed")
    receivable_status = fetchone(cur, "SELECT status FROM receivable_checks WHERE id=?", (receivable_check_id,))[0]
    assert_true(receivable_status == "bounced", "receivable check did not reach bounced state")

    response = client.post(
        "/banks/checks/payable",
        data={
            "doc_no": "PCH-001",
            "check_number": "CHK-P-1",
            "bank_id": str(bank_1_id),
            "supplier_id": str(supplier_id),
            "due_date": "2026-05-12",
            "amount": "140",
        },
        follow_redirects=False,
    )
    assert_true(response.status_code in (302, 303), "payable check creation failed")
    payable_check_id = fetchone(cur, "SELECT id FROM payable_checks WHERE check_number='CHK-P-1'")[0]
    response = client.post(
        f"/banks/checks/payable/{payable_check_id}/action",
        data={"action": "deliver"},
        follow_redirects=False,
    )
    assert_true(response.status_code in (302, 303), "payable check delivery failed")
    response = client.post(
        f"/banks/checks/payable/{payable_check_id}/action",
        data={"action": "cash"},
        follow_redirects=False,
    )
    assert_true(response.status_code in (302, 303), "payable check cashing failed")
    payable_status = fetchone(cur, "SELECT status, bank_transaction_id FROM payable_checks WHERE id=?", (payable_check_id,))
    assert_true(payable_status[0] == "cashed", "payable check did not reach cashed state")
    assert_true(payable_status[1] is not None, "payable check was not linked to a bank transaction")

    journal_rows = fetchone(cur, "SELECT COUNT(*) FROM journal WHERE source_type IN ('bank_transaction','bank_transfer','receivable_check','payable_check','receivable_check_deposit','receivable_check_bounce','payable_check_cash')")[0]
    assert_true(journal_rows > 0, "bank operations did not generate journal entries")

    with client.session_transaction() as session:
        session["user_id"] = 2
        session["username"] = "viewer"
        session["role"] = "viewer"
    response = client.post(
        "/banks/transactions",
        data={
            "txn_type": "deposit",
            "bank_id": str(bank_1_id),
            "txn_date": "2026-05-07",
            "doc_no": "BTX-VIEW-1",
            "amount": "10",
            "counterparty_account_id": str(customer_control),
        },
        follow_redirects=False,
    )
    assert_true(response.status_code in (302, 303), "viewer write guard did not redirect")
    blocked_count = fetchone(cur, "SELECT COUNT(*) FROM bank_transactions WHERE doc_no='BTX-VIEW-1'")[0]
    assert_true(blocked_count == 0, "viewer was able to create bank transaction")

    conn.close()
    appmod.DB_PATH = old_db_path
    appmod.MODULE_DEPS["DB_PATH"] = old_module_db_path
    shutil.rmtree(temp_dir, ignore_errors=True)
    print("invoice_workflow_test: ok")


if __name__ == "__main__":
    main()
