import shutil
import sys
from pathlib import Path

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


def route_exists(flask_app, path, method="GET"):
    adapter = flask_app.url_map.bind("localhost")
    try:
        adapter.match(path, method=method)
        return True
    except Exception:
        return False


def cleanup_temp_db(temp_db: Path):
    for suffix in ("", "-journal", "-wal", "-shm"):
        cleanup_path = Path(str(temp_db) + suffix) if suffix else temp_db
        if cleanup_path.exists():
            cleanup_path.unlink()


def main():
    source_db = PROJECT_ROOT / "database.db"
    temp_db = TMP_ROOT / "banks_module_test.db"
    cleanup_temp_db(temp_db)
    shutil.copy2(source_db, temp_db)

    old_db_path = appmod.DB_PATH
    old_module_db_path = appmod.MODULE_DEPS.get("DB_PATH")
    conn = None
    try:
        appmod.DB_PATH = str(temp_db)
        appmod.MODULE_DEPS["DB_PATH"] = str(temp_db)
        appmod.run_migrations(str(temp_db))
        appmod.init_db()
        appmod.app.config["TESTING"] = True

        client = appmod.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "banks-module-test"
            session["role"] = "admin"

        for path in (
            "/banks",
            "/banks/transactions",
            "/banks/transfers",
            "/banks/statements",
            "/banks/reconciliation",
            "/banks/checks/receivable",
            "/banks/checks/payable",
        ):
            assert_true(route_exists(appmod.app, path), f"missing route: {path}")

        conn = appmod.db()
        cur = conn.cursor()

        for table_name in (
            "banks",
            "bank_transactions",
            "bank_reconciliations",
            "receivable_checks",
            "payable_checks",
        ):
            assert_true(
                fetchone(cur, "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)) is not None,
                f"missing table: {table_name}",
            )

        cur.execute("INSERT INTO customers(name,tax_id) VALUES (?,?)", ("عميل اختبار الشيكات", "C-TAX-001"))
        customer_id = cur.lastrowid
        cur.execute("INSERT INTO suppliers(name,tax_id) VALUES (?,?)", ("مورد اختبار الشيكات", "S-TAX-001"))
        supplier_id = cur.lastrowid
        conn.commit()

        treasury_gl = fetchone(cur, "SELECT id FROM accounts WHERE code='1100' LIMIT 1")
        treasury_gl = treasury_gl[0] if treasury_gl else None
        bank_gl_1 = fetchone(cur, "SELECT id FROM accounts WHERE code IN ('1200','1210','1110','1120') ORDER BY code LIMIT 1")
        bank_gl_1 = bank_gl_1[0] if bank_gl_1 else fetchone(cur, "SELECT id FROM accounts ORDER BY code LIMIT 1")[0]
        bank_gl_2 = fetchone(
            cur,
            "SELECT id FROM accounts WHERE code IN ('1210','1120','1110','1200') AND id<>? ORDER BY code LIMIT 1",
            (bank_gl_1,),
        )
        bank_gl_2 = bank_gl_2[0] if bank_gl_2 else fetchone(cur, "SELECT id FROM accounts WHERE id<>? ORDER BY code LIMIT 1", (bank_gl_1,))[0]
        customer_control = fetchone(cur, "SELECT id FROM accounts WHERE code='1300' LIMIT 1")
        customer_control = customer_control[0] if customer_control else treasury_gl or bank_gl_2
        expense_gl = fetchone(cur, "SELECT id FROM accounts WHERE code IN ('5295','6100') ORDER BY code LIMIT 1")
        expense_gl = expense_gl[0] if expense_gl else customer_control

        response = client.post(
            "/banks",
            data={
                "name": "بنك اختبار 1",
                "branch": "الرئيسي",
                "account_number": "A-100",
                "currency": "EGP",
                "opening_balance": "1000",
                "gl_account_id": str(bank_gl_1),
                "is_active": "1",
            },
            follow_redirects=False,
        )
        assert_true(response.status_code in (302, 303), "failed to create first bank")
        response = client.post(
            "/banks",
            data={
                "name": "بنك اختبار 2",
                "branch": "فرع 2",
                "account_number": "A-200",
                "currency": "EGP",
                "opening_balance": "500",
                "gl_account_id": str(bank_gl_2),
                "is_active": "1",
            },
            follow_redirects=False,
        )
        assert_true(response.status_code in (302, 303), "failed to create second bank")

        bank_1_id = fetchone(cur, "SELECT id FROM banks WHERE name='بنك اختبار 1'")[0]
        bank_2_id = fetchone(cur, "SELECT id FROM banks WHERE name='بنك اختبار 2'")[0]

        initial_journal = fetchone(cur, "SELECT COUNT(*) FROM journal")[0]
        initial_ledger = fetchone(cur, "SELECT COUNT(*) FROM ledger")[0]

        response = client.post(
            "/banks/transactions",
            data={
                "txn_type": "deposit",
                "bank_id": str(bank_1_id),
                "txn_date": "2026-05-05",
                "doc_no": "BTX-DEP-001",
                "amount": "250",
                "description": "إيداع بنكي اختبار",
                "counterparty_account_id": str(customer_control),
            },
            follow_redirects=False,
        )
        assert_true(response.status_code in (302, 303), "deposit failed")
        deposit_txn = fetchone(cur, "SELECT id,journal_id,balance_after FROM bank_transactions WHERE txn_type='deposit' AND doc_no='BTX-DEP-001'")
        assert_true(deposit_txn is not None and deposit_txn[1] is not None, "deposit transaction missing journal link")

        after_deposit_journal = fetchone(cur, "SELECT COUNT(*) FROM journal")[0]
        after_deposit_ledger = fetchone(cur, "SELECT COUNT(*) FROM ledger")[0]
        assert_true(after_deposit_journal > initial_journal, "deposit did not create journal entry")
        assert_true(after_deposit_ledger > initial_ledger, "deposit did not rebuild ledger")

        response = client.post(
            "/banks/transactions",
            data={
                "txn_type": "withdrawal",
                "bank_id": str(bank_1_id),
                "txn_date": "2026-05-06",
                "doc_no": "BTX-WDR-001",
                "amount": "75",
                "description": "سحب بنكي اختبار",
                "counterparty_account_id": str(expense_gl),
            },
            follow_redirects=False,
        )
        assert_true(response.status_code in (302, 303), "withdrawal failed")
        withdrawal_txn = fetchone(cur, "SELECT id,journal_id,signed_amount FROM bank_transactions WHERE txn_type='withdrawal' AND doc_no='BTX-WDR-001'")
        assert_true(withdrawal_txn is not None and withdrawal_txn[1] is not None, "withdrawal transaction missing journal link")
        assert_true(float(withdrawal_txn[2]) < 0, "withdrawal signed amount should be negative")

        journal_after_withdrawal = fetchone(cur, "SELECT COUNT(*) FROM journal")[0]
        ledger_after_withdrawal = fetchone(cur, "SELECT COUNT(*) FROM ledger")[0]
        assert_true(journal_after_withdrawal > after_deposit_journal, "withdrawal did not create journal entry")
        assert_true(ledger_after_withdrawal > after_deposit_ledger, "withdrawal did not rebuild ledger")

        response = client.post(
            "/banks/transfers",
            data={
                "source_bank_id": str(bank_1_id),
                "target_bank_id": str(bank_2_id),
                "txn_date": "2026-05-07",
                "doc_no": "BTR-001",
                "amount": "125",
                "description": "تحويل بنك لبنك اختبار",
                "reference_no": "REF-BTR-1",
            },
            follow_redirects=False,
        )
        assert_true(response.status_code in (302, 303), "bank transfer failed")
        transfer_out = fetchone(cur, "SELECT id,journal_id,related_bank_id FROM bank_transactions WHERE txn_type='bank_to_bank_out' AND doc_no='BTR-001'")
        transfer_in = fetchone(cur, "SELECT id,journal_id,related_bank_id FROM bank_transactions WHERE txn_type='deposit' AND doc_no='BTR-001'")
        assert_true(transfer_out is not None and transfer_out[1] is not None, "transfer out transaction missing journal link")
        assert_true(transfer_in is not None and transfer_in[1] is not None, "transfer in transaction missing journal link")
        assert_true(transfer_out[2] == bank_2_id, "transfer out does not point to target bank")
        assert_true(transfer_in[2] == bank_1_id, "transfer in does not point to source bank")

        journal_after_transfer = fetchone(cur, "SELECT COUNT(*) FROM journal")[0]
        ledger_after_transfer = fetchone(cur, "SELECT COUNT(*) FROM ledger")[0]
        assert_true(journal_after_transfer > journal_after_withdrawal, "bank transfer did not create journal entry")
        assert_true(ledger_after_transfer > ledger_after_withdrawal, "bank transfer did not rebuild ledger")

        response = client.post(
            "/banks/reconciliation",
            data={
                "bank_id": str(bank_1_id),
                "statement_date": "2026-05-08",
                "from_date": "2026-05-05",
                "to_date": "2026-05-07",
                "doc_no": "BRC-001",
                "statement_balance": "1050",
                "lines_text": "2026-05-05|250|BTX-DEP-001|إيداع\n2026-05-06|75|BTX-WDR-001|سحب",
            },
            follow_redirects=False,
        )
        assert_true(response.status_code in (302, 303), "bank reconciliation failed")
        reconciliation_row = fetchone(cur, "SELECT id FROM bank_reconciliations WHERE doc_no='BRC-001'")
        assert_true(reconciliation_row is not None, "reconciliation row was not created")
        matched_lines = fetchone(cur, "SELECT COUNT(*) FROM bank_reconciliation_lines WHERE reconciliation_id=? AND match_status='matched'", (reconciliation_row[0],))[0]
        assert_true(matched_lines >= 2, "reconciliation did not match expected bank lines")

        response = client.post(
            "/banks/checks/receivable",
            data={
                "doc_no": "RCH-001",
                "check_number": "CHK-R-001",
                "bank_id": str(bank_1_id),
                "customer_id": str(customer_id),
                "due_date": "2026-05-10",
                "amount": "90",
                "notes": "شيك قبض اختبار",
            },
            follow_redirects=False,
        )
        assert_true(response.status_code in (302, 303), "receivable check creation failed")
        receivable_check = fetchone(cur, "SELECT id,status,received_journal_id FROM receivable_checks WHERE check_number='CHK-R-001'")
        assert_true(receivable_check is not None and receivable_check[2] is not None, "receivable check missing journal entry")
        response = client.post(
            f"/banks/checks/receivable/{receivable_check[0]}/action",
            data={"action": "deposit", "doc_no": "BTX-RCH-DEP-001"},
            follow_redirects=False,
        )
        assert_true(response.status_code in (302, 303), "receivable check deposit failed")
        response = client.post(
            f"/banks/checks/receivable/{receivable_check[0]}/action",
            data={"action": "bounce", "doc_no": "BTX-RCH-BOUNCE-001"},
            follow_redirects=False,
        )
        assert_true(response.status_code in (302, 303), "receivable check bounce failed")
        receivable_status = fetchone(cur, "SELECT status,bounce_journal_id FROM receivable_checks WHERE id=?", (receivable_check[0],))
        assert_true(receivable_status[0] == "bounced", "receivable check did not reach bounced state")
        assert_true(receivable_status[1] is not None, "receivable check bounce did not generate journal entry")

        response = client.post(
            "/banks/checks/payable",
            data={
                "doc_no": "PCH-001",
                "check_number": "CHK-P-001",
                "bank_id": str(bank_1_id),
                "supplier_id": str(supplier_id),
                "due_date": "2026-05-12",
                "amount": "140",
                "notes": "شيك دفع اختبار",
            },
            follow_redirects=False,
        )
        assert_true(response.status_code in (302, 303), "payable check creation failed")
        payable_check = fetchone(cur, "SELECT id,status,issue_journal_id FROM payable_checks WHERE check_number='CHK-P-001'")
        assert_true(payable_check is not None and payable_check[2] is not None, "payable check missing issue journal entry")
        response = client.post(
            f"/banks/checks/payable/{payable_check[0]}/action",
            data={"action": "deliver"},
            follow_redirects=False,
        )
        assert_true(response.status_code in (302, 303), "payable check deliver failed")
        response = client.post(
            f"/banks/checks/payable/{payable_check[0]}/action",
            data={"action": "cash", "doc_no": "BTX-PCH-CASH-001"},
            follow_redirects=False,
        )
        assert_true(response.status_code in (302, 303), "payable check cash failed")
        payable_status = fetchone(cur, "SELECT status,cash_journal_id,bank_transaction_id FROM payable_checks WHERE id=?", (payable_check[0],))
        assert_true(payable_status[0] == "cashed", "payable check did not reach cashed state")
        assert_true(payable_status[1] is not None, "payable check cash did not generate journal entry")
        assert_true(payable_status[2] is not None, "payable check was not linked to bank transaction")

        before_duplicate = fetchone(cur, "SELECT COUNT(*) FROM bank_transactions WHERE txn_type='deposit' AND doc_no='BTX-DUP-001'")[0]
        response = client.post(
            "/banks/transactions",
            data={
                "txn_type": "deposit",
                "bank_id": str(bank_1_id),
                "txn_date": "2026-05-08",
                "doc_no": "BTX-DUP-001",
                "amount": "50",
                "description": "اختبار تكرار 1",
                "counterparty_account_id": str(customer_control),
            },
            follow_redirects=True,
        )
        assert_true(response.status_code == 200, "first duplicate-guard submission failed")
        after_first = fetchone(cur, "SELECT COUNT(*) FROM bank_transactions WHERE txn_type='deposit' AND doc_no='BTX-DUP-001'")[0]
        response = client.post(
            "/banks/transactions",
            data={
                "txn_type": "deposit",
                "bank_id": str(bank_1_id),
                "txn_date": "2026-05-08",
                "doc_no": "BTX-DUP-001",
                "amount": "50",
                "description": "اختبار تكرار 2",
                "counterparty_account_id": str(customer_control),
            },
            follow_redirects=True,
        )
        assert_true(response.status_code == 200, "second duplicate-guard submission failed")
        after_second = fetchone(cur, "SELECT COUNT(*) FROM bank_transactions WHERE txn_type='deposit' AND doc_no='BTX-DUP-001'")[0]
        assert_true(after_first == before_duplicate + 1, "first duplicate test document was not created")
        assert_true(after_second == after_first, "duplicate document number was not blocked")

        statement_response = client.get(f"/banks/statements?bank_id={bank_1_id}")
        assert_true(statement_response.status_code == 200, "bank statement screen failed")
        assert_true("BTX-DEP-001".encode("utf-8") in statement_response.data, "bank statement does not show deposit document")

        bank_1_balance = float(fetchone(cur, "SELECT current_balance FROM banks WHERE id=?", (bank_1_id,))[0] or 0)
        bank_2_balance = float(fetchone(cur, "SELECT current_balance FROM banks WHERE id=?", (bank_2_id,))[0] or 0)
        assert_true(bank_1_balance > 0, "first bank current balance was not updated")
        assert_true(bank_2_balance > 0, "second bank current balance was not updated after transfer")
        print("banks_module_test: ok")
    finally:
        if conn is not None:
            conn.close()
        appmod.DB_PATH = old_db_path
        appmod.MODULE_DEPS["DB_PATH"] = old_module_db_path
        cleanup_temp_db(temp_db)


if __name__ == "__main__":
    main()
