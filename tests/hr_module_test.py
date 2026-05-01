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


def fetchone(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchone()


def main():
    source_db = PROJECT_ROOT / "database.db"
    temp_dir = Path(tempfile.mkdtemp(prefix="erp-hr-test-", dir=str(PROJECT_ROOT)))
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
        session["username"] = "hr-test-admin"
        session["role"] = "admin"

    conn = appmod.db()
    cur = conn.cursor()
    cur.execute("DELETE FROM payroll_lines")
    cur.execute("DELETE FROM payroll_runs")
    cur.execute("DELETE FROM employees")
    conn.commit()

    departments_page = client.get("/employees")
    assert_true(departments_page.status_code == 200, "صفحة الموظفين لا تعمل")
    html = departments_page.get_data(as_text=True)
    for department_name in ("الإدارة", "الحسابات", "المبيعات", "الموارد البشرية"):
        assert_true(department_name in html, f"القسم الافتراضي {department_name} غير ظاهر")

    create_first = client.post(
        "/employees",
        data={
            "action": "add_employee",
            "name": "موظف أول",
            "department_id": str(fetchone(cur, "SELECT id FROM departments WHERE name='الإدارة'")[0]),
            "job_title": "محاسب",
            "hire_date": "2026-05-01",
            "base_salary": "5000",
            "allowances": "500",
            "insurance_employee": "250",
            "insurance_company": "300",
            "tax": "100",
            "status": "active",
            "notes": "اختبار أول",
        },
        follow_redirects=False,
    )
    assert_true(create_first.status_code in (302, 303), "فشل إنشاء الموظف الأول")
    first_employee = fetchone(cur, "SELECT id, employee_code, code FROM employees ORDER BY id ASC LIMIT 1")
    assert_true(first_employee[1] == "EMP-001", "لم يتم توليد EMP-001 للموظف الأول")

    create_second = client.post(
        "/employees",
        data={
            "action": "add_employee",
            "name": "موظف ثان",
            "department_id": str(fetchone(cur, "SELECT id FROM departments WHERE name='المبيعات'")[0]),
            "job_title": "مندوب",
            "hire_date": "2026-05-02",
            "base_salary": "3000",
            "allowances": "0",
            "insurance_employee": "0",
            "insurance_company": "0",
            "tax": "0",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert_true(create_second.status_code in (302, 303), "فشل إنشاء الموظف الثاني")
    second_employee = fetchone(cur, "SELECT id, employee_code FROM employees ORDER BY id DESC LIMIT 1")
    assert_true(second_employee[1] == "EMP-002", "لم يتم توليد EMP-002 للموظف الثاني")

    cur.execute("UPDATE employees SET status='inactive' WHERE id=?", (second_employee[0],))
    conn.commit()

    employees_page = client.get("/employees")
    assert_true(employees_page.status_code == 200, "صفحة الموظفين بعد الإضافة لا تعمل")
    employees_html = employees_page.get_data(as_text=True)
    assert_true(f"/employees/{first_employee[0]}/edit" in employees_html, "زر التعديل غير ظاهر")
    assert_true(f"/employees/{first_employee[0]}/delete" in employees_html, "زر الحذف غير ظاهر")

    payroll_create = client.post(
        "/payroll",
        data={
            "period": "2026-05",
            "date": "2026-05-31",
            "payment_method": "accrued",
            "notes": "اختبار كشف مرتب",
        },
        follow_redirects=False,
    )
    assert_true(payroll_create.status_code in (302, 303), "فشل إنشاء كشف المرتبات")

    run = fetchone(
        cur,
        "SELECT id, status, posting_status, total_gross, total_employee_deductions, total_company_insurance, total_net FROM payroll_runs ORDER BY id DESC LIMIT 1",
    )
    assert_true(run[1] == "draft", "كشف المرتبات يجب أن يبدأ كمسودة")
    assert_true(run[2] == "unposted", "posting_status يجب أن يبدأ unposted")
    assert_true(round(float(run[3]), 2) == 5500.00, "إجمالي المستحقات غير صحيح")
    assert_true(round(float(run[4]), 2) == 350.00, "إجمالي الاستقطاعات غير صحيح")
    assert_true(round(float(run[5]), 2) == 300.00, "حصة الشركة في التأمينات غير صحيحة")
    assert_true(round(float(run[6]), 2) == 5150.00, "صافي المرتب غير صحيح")

    payroll_line = fetchone(
        cur,
        """
        SELECT base_salary, allowances, insurance_employee, insurance_company, tax, total_deductions, net_salary
        FROM payroll_lines
        WHERE run_id=?
        """,
        (run[0],),
    )
    assert_true(round(float(payroll_line[5]), 2) == 350.00, "إجمالي خصومات سطر المرتب غير صحيح")
    assert_true(round(float(payroll_line[6]), 2) == 5150.00, "صافي سطر المرتب غير صحيح")

    payroll_post = client.post(f"/payroll/{run[0]}/post", follow_redirects=False)
    assert_true(payroll_post.status_code in (302, 303), "فشل اعتماد كشف المرتبات")
    posted_run = fetchone(
        cur,
        """
        SELECT status, posting_status, journal_id, allowances_journal_id, tax_journal_id,
               insurance_journal_id, company_insurance_journal_id, deductions_journal_id
        FROM payroll_runs
        WHERE id=?
        """,
        (run[0],),
    )
    assert_true(posted_run[0] == "posted", "حالة الكشف بعد الاعتماد غير صحيحة")
    assert_true(posted_run[1] == "posted", "posting_status بعد الاعتماد غير صحيح")
    assert_true(posted_run[2] is not None, "قيد المرتب الأساسي لم يُنشأ")
    assert_true(posted_run[3] is not None, "قيد البدلات لم يُنشأ")
    assert_true(posted_run[4] is not None, "قيد الضرائب لم يُنشأ")
    assert_true(posted_run[5] is not None, "قيد تأمينات الموظف لم يُنشأ")
    assert_true(posted_run[6] is not None, "قيد حصة الشركة في التأمينات لم يُنشأ")

    cur.execute(
        """
        SELECT da.code, ca.code, amount
        FROM journal j
        JOIN accounts da ON da.id=j.debit_account_id
        JOIN accounts ca ON ca.id=j.credit_account_id
        WHERE j.source_type='payroll' AND j.source_id=?
        ORDER BY j.id
        """,
        (run[0],),
    )
    journal_pairs = {(row[0], row[1], round(float(row[2]), 2)) for row in cur.fetchall()}
    expected_pairs = {
        ("5110", "2310", 5000.00),
        ("5115", "2310", 500.00),
        ("2310", "2220", 250.00),
        ("2310", "2340", 100.00),
        ("5170", "2220", 300.00),
    }
    assert_true(expected_pairs.issubset(journal_pairs), "القيود المحاسبية للمرتبات غير مكتملة أو غير صحيحة")

    repost = client.post(f"/payroll/{run[0]}/post", follow_redirects=False)
    assert_true(repost.status_code in (302, 303), "فشل اختبار منع إعادة الترحيل")
    cur.execute("SELECT COUNT(*) FROM journal WHERE source_type='payroll' AND source_id=?", (run[0],))
    journal_count_after_repost = cur.fetchone()[0]
    assert_true(journal_count_after_repost == len(journal_pairs), "تم إنشاء قيود إضافية عند إعادة الترحيل")

    payslip = client.get(f"/payroll/{run[0]}/payslip/{first_employee[0]}")
    assert_true(payslip.status_code == 200, "صفحة شيت المرتب لا تعمل")
    payslip_html = payslip.get_data(as_text=True)
    assert_true("شيت مرتب" in payslip_html, "عنوان شيت المرتب غير ظاهر")
    assert_true("window.print()" in payslip_html, "زر الطباعة غير موجود في شيت المرتب")
    assert_true("EMP-001" in payslip_html, "كود الموظف غير ظاهر في شيت المرتب")

    conn.close()
    print(
        json.dumps(
            {
                "temp_db": str(temp_db),
                "run_id": run[0],
                "first_employee_code": first_employee[1],
                "second_employee_code": second_employee[1],
                "journal_pairs": sorted(list(journal_pairs)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
