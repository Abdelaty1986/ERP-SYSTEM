import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def scalar(cur: sqlite3.Cursor, sql: str, params=()):
    cur.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row else None


def main():
    source_db = PROJECT_ROOT / "database.db"
    temp_dir = Path(tempfile.mkdtemp(prefix="erp-hr-egypt-auto-", dir=str(PROJECT_ROOT)))
    temp_db = temp_dir / "database_test.db"
    shutil.copy2(source_db, temp_db)
    os.environ["ERP_DB_PATH"] = str(temp_db)

    import app as appmod

    appmod.DB_PATH = str(temp_db)
    appmod.MODULE_DEPS["DB_PATH"] = str(temp_db)
    appmod.init_db()
    appmod.run_migrations(str(temp_db))
    appmod.app.config["TESTING"] = True

    client = appmod.app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = 1
        session["username"] = "hr-egypt-auto"
        session["role"] = "admin"

    conn = connect(temp_db)
    cur = conn.cursor()
    cur.execute("DELETE FROM hr_payroll_lines")
    cur.execute("DELETE FROM hr_payroll_runs")
    cur.execute("DELETE FROM hr_salary_adjustments")
    cur.execute("DELETE FROM hr_attendance")
    cur.execute("DELETE FROM hr_employees")
    conn.commit()

    admin_dept = scalar(cur, "SELECT id FROM hr_departments ORDER BY id LIMIT 1")
    assert_true(admin_dept is not None, "missing default department")

    rules_response = client.post(
        "/hr/payroll",
        data={
            "form_action": "update_rules",
            "monthly_work_days": "26",
            "absent_day_deduction_rate": "1",
            "late_deduction_per_min": "0",
            "overtime_rate_per_hour": "0",
            "overtime_multiplier": "1.35",
            "annual_salary_tax_exemption": "20000",
            "employee_insurance_rate": "0.11",
            "employer_insurance_rate": "0.1875",
            "social_insurance_min_salary": "2700",
            "social_insurance_max_salary": "16700",
            "salary_expense_account_code": "5110",
            "variable_compensation_account_code": "5115",
            "employer_insurance_expense_account_code": "5116",
            "salary_payable_account_code": "2310",
            "insurance_payable_account_code": "2220",
            "tax_payable_account_code": "2340",
            "deductions_payable_account_code": "2330",
            "cash_account_code": "1100",
            "bank_account_code": "1200",
            "adjustment_month": "2026-05",
        },
        follow_redirects=False,
    )
    assert_true(rules_response.status_code in (302, 303), "failed to update payroll rules")

    employee_response = client.post(
        "/hr/employees/add",
        data={
            "full_name": "Auto Payroll Employee",
            "department_id": str(admin_dept),
            "job_title": "Accountant",
            "hire_date": "2026-05-01",
            "base_salary": "6000",
            "work_start": "09:00",
            "work_end": "17:00",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert_true(employee_response.status_code in (302, 303), "failed to create employee")
    employee_id = scalar(cur, "SELECT id FROM hr_employees ORDER BY id DESC LIMIT 1")
    assert_true(employee_id is not None, "employee was not created")

    attendance_response = client.post(
        "/hr/attendance",
        data={
            "employee_id": str(employee_id),
            "attendance_date": "2026-05-05",
            "check_in": "10:00",
            "check_out": "17:00",
            "status": "present",
            "notes": "auto payroll test",
        },
        follow_redirects=False,
    )
    assert_true(attendance_response.status_code in (302, 303), "failed to create attendance")

    generate = client.post(
        "/hr/payroll/generate",
        data={
            "payroll_month": "2026-05",
            "run_date": "2026-05-31",
            "payment_method": "accrued",
            "notes": "Egypt auto payroll verification",
        },
        follow_redirects=False,
    )
    assert_true(generate.status_code in (302, 303), "failed to generate payroll")

    run = cur.execute(
        "SELECT id, total_gross, total_deductions, total_net, status, posting_status FROM hr_payroll_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert_true(run is not None, "payroll run missing")
    assert_true(run["status"] == "draft", "run should start in draft status")
    assert_true(run["posting_status"] == "unposted", "posting status should start unposted")

    line = cur.execute(
        """
        SELECT
            hourly_rate,
            scheduled_work_hours,
            insurance_amount,
            employer_insurance_amount,
            insurance_base_salary,
            tax_amount,
            late_deduction,
            absence_deduction,
            taxable_salary,
            total_deductions,
            net_salary
        FROM hr_payroll_lines
        WHERE run_id=? AND employee_id=?
        """,
        (run["id"], employee_id),
    ).fetchone()
    assert_true(line is not None, "payroll line missing")
    assert_true(round(float(line["hourly_rate"]), 2) == 28.85, "unexpected hourly rate")
    assert_true(round(float(line["scheduled_work_hours"]), 2) == 8.00, "unexpected scheduled work hours")
    assert_true(round(float(line["insurance_amount"]), 2) == 660.00, "unexpected employee insurance")
    assert_true(round(float(line["employer_insurance_amount"]), 2) == 1125.00, "unexpected employer insurance")
    assert_true(round(float(line["insurance_base_salary"]), 2) == 6000.00, "unexpected insurance base")
    assert_true(round(float(line["late_deduction"]), 2) == 28.85, "unexpected late deduction")
    assert_true(round(float(line["absence_deduction"]), 2) == 0.00, "absence deduction should be zero")
    assert_true(round(float(line["tax_amount"]), 2) == 31.12, "unexpected salary tax")
    assert_true(round(float(line["taxable_salary"]), 2) == 5971.15, "unexpected taxable salary")
    assert_true(round(float(line["total_deductions"]), 2) == 719.97, "unexpected total deductions")
    assert_true(round(float(line["net_salary"]), 2) == 5280.03, "unexpected net salary")

    payslip = client.get(f"/hr/payroll/{run['id']}/payslip/{employee_id}")
    assert_true(payslip.status_code == 200, "failed to open payslip")
    payslip_html = payslip.get_data(as_text=True)
    assert_true("28.85" in payslip_html, "hourly rate is not visible in payslip")
    assert_true("1125.00" in payslip_html, "employer insurance is not visible in payslip")
    assert_true("5971.15" in payslip_html, "taxable salary is not visible in payslip")

    post_run = client.post(f"/hr/payroll/{run['id']}/post", follow_redirects=False)
    assert_true(post_run.status_code in (302, 303), "failed to post payroll")

    journal_rows = cur.execute(
        """
        SELECT da.code AS debit_code, ca.code AS credit_code, ROUND(j.amount, 2) AS amount
        FROM journal j
        JOIN accounts da ON da.id = j.debit_account_id
        JOIN accounts ca ON ca.id = j.credit_account_id
        WHERE j.source_type='hr_payroll' AND j.source_id=?
        ORDER BY j.id
        """,
        (run["id"],),
    ).fetchall()
    journal_pairs = {(row["debit_code"], row["credit_code"], float(row["amount"])) for row in journal_rows}
    expected_pairs = {
        ("5110", "2310", 6000.00),
        ("2310", "2220", 660.00),
        ("2310", "2340", 31.12),
        ("2310", "2330", 28.85),
        ("5116", "2220", 1125.00),
    }
    assert_true(expected_pairs.issubset(journal_pairs), "posted payroll journals are incomplete")

    conn.close()
    print(
        json.dumps(
            {
                "run_id": run["id"],
                "hourly_rate": float(line["hourly_rate"]),
                "employee_insurance": float(line["insurance_amount"]),
                "employer_insurance": float(line["employer_insurance_amount"]),
                "salary_tax": float(line["tax_amount"]),
                "late_deduction": float(line["late_deduction"]),
                "journal_pairs": sorted(list(journal_pairs)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
