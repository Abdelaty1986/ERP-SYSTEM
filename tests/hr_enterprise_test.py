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
    temp_dir = Path(tempfile.mkdtemp(prefix="erp-hr-enterprise-test-", dir=str(PROJECT_ROOT)))
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
        session["username"] = "hr-enterprise-admin"
        session["role"] = "admin"

    first_page = client.get("/hr/employees")
    assert_true(first_page.status_code == 200, "فتح /hr/employees يجب أن يعمل بدون 500")
    html = first_page.get_data(as_text=True)
    assert_true("allowances" not in html, "صفحة /hr/employees لا يجب أن تعتمد على allowances من جدول الموظفين")

    conn = connect(temp_db)
    cur = conn.cursor()
    cur.execute("DELETE FROM hr_payroll_lines")
    cur.execute("DELETE FROM hr_payroll_runs")
    cur.execute("DELETE FROM hr_salary_adjustments")
    cur.execute("DELETE FROM hr_employees")
    conn.commit()

    admin_dept = scalar(cur, "SELECT id FROM hr_departments WHERE name='الإدارة'")
    sales_dept = scalar(cur, "SELECT id FROM hr_departments WHERE name='المبيعات'")
    hr_dept = scalar(cur, "SELECT id FROM hr_departments WHERE name='الموارد البشرية'")
    assert_true(admin_dept is not None and sales_dept is not None and hr_dept is not None, "الأقسام الافتراضية غير مكتملة")

    create_one = client.post(
        "/hr/employees/add",
        data={
            "full_name": "أحمد علي",
            "department_id": str(admin_dept),
            "job_title": "محاسب",
            "hire_date": "2026-05-01",
            "base_salary": "5000",
            "phone": "01000000001",
            "email": "ahmed@example.com",
            "national_id": "29901011234567",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert_true(create_one.status_code in (302, 303), "فشل إنشاء الموظف الأول")
    first_employee = cur.execute("SELECT id, employee_code FROM hr_employees ORDER BY id ASC LIMIT 1").fetchone()
    assert_true(first_employee["employee_code"] == "EMP-001", "الموظف الأول يجب أن يأخذ EMP-001")

    create_two = client.post(
        "/hr/employees/add",
        data={
            "full_name": "سارة حسن",
            "department_id": str(sales_dept),
            "job_title": "مندوب مبيعات",
            "hire_date": "2026-05-02",
            "base_salary": "3200",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert_true(create_two.status_code in (302, 303), "فشل إنشاء الموظف الثاني")
    second_employee = cur.execute("SELECT id, employee_code FROM hr_employees ORDER BY id DESC LIMIT 1").fetchone()
    assert_true(second_employee["employee_code"] == "EMP-002", "الموظف الثاني يجب أن يأخذ EMP-002")

    create_three = client.post(
        "/hr/employees/add",
        data={
            "full_name": "منى السيد",
            "department_id": str(hr_dept),
            "job_title": "أخصائي موارد بشرية",
            "hire_date": "2026-05-03",
            "base_salary": "2800",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert_true(create_three.status_code in (302, 303), "فشل إنشاء الموظف الثالث")
    third_employee = cur.execute("SELECT id FROM hr_employees WHERE full_name='منى السيد'").fetchone()
    cur.execute("UPDATE hr_employees SET is_active=0, status='inactive' WHERE id=?", (second_employee["id"],))
    conn.commit()

    listing = client.get("/hr/employees")
    assert_true(listing.status_code == 200, "قائمة موظفي HR لا تعمل")
    listing_html = listing.get_data(as_text=True)
    assert_true(f"/hr/employees/{first_employee['id']}" in listing_html, "زر عرض الموظف غير ظاهر")
    assert_true(f"/hr/employees/{first_employee['id']}/edit" in listing_html, "زر تعديل الموظف غير ظاهر")
    assert_true(f"/hr/employees/{first_employee['id']}/delete" in listing_html, "زر حذف الموظف غير ظاهر")

    edit = client.post(
        f"/hr/employees/{first_employee['id']}/edit",
        data={
            "full_name": "أحمد علي إبراهيم",
            "department_id": str(admin_dept),
            "job_title": "رئيس حسابات",
            "hire_date": "2026-05-01",
            "base_salary": "5000",
            "phone": "01000000009",
            "email": "ahmed.i@example.com",
            "national_id": "29901011234567",
            "work_start": "09:00",
            "work_end": "17:00",
            "annual_leave_balance": "21",
            "status": "active",
            "notes": "تمت الترقية",
        },
        follow_redirects=False,
    )
    assert_true(edit.status_code in (302, 303), "فشل تعديل الموظف")
    updated = cur.execute("SELECT full_name, job_title, phone FROM hr_employees WHERE id=?", (first_employee["id"],)).fetchone()
    assert_true(updated["full_name"] == "أحمد علي إبراهيم", "اسم الموظف لم يتحدث")
    assert_true(updated["job_title"] == "رئيس حسابات", "وظيفة الموظف لم تتحدث")

    delete_third = client.post(f"/hr/employees/{third_employee['id']}/delete", follow_redirects=False)
    assert_true(delete_third.status_code in (302, 303), "فشل تنفيذ soft delete")
    third_status = cur.execute("SELECT is_active, status FROM hr_employees WHERE id=?", (third_employee["id"],)).fetchone()
    assert_true(int(third_status["is_active"]) == 0 and third_status["status"] == "inactive", "soft delete لم يعمل بشكل صحيح")

    for adjustment_type, amount, title in [
        ("allowance", "300", "بدل انتقال"),
        ("bonus", "200", "علاوة شهرية"),
        ("overtime", "80", "إضافي"),
        ("insurance", "150", "تأمينات"),
        ("tax", "50", "ضريبة كسب عمل"),
        ("loan", "100", "سلفة"),
        ("penalty", "25", "جزاء"),
        ("deduction", "75", "استقطاع آخر"),
    ]:
        response = client.post(
            "/hr/payroll",
            data={
                "employee_id": str(first_employee["id"]),
                "adjustment_month": "2026-05",
                "adjustment_type": adjustment_type,
                "title": title,
                "amount": amount,
            },
            follow_redirects=False,
        )
        assert_true(response.status_code in (302, 303), f"فشل حفظ تسوية {adjustment_type}")

    generate = client.post(
        "/hr/payroll/generate",
        data={
            "payroll_month": "2026-05",
            "run_date": "2026-05-31",
            "payment_method": "accrued",
            "notes": "اختبار مسير HR Enterprise",
        },
        follow_redirects=False,
    )
    assert_true(generate.status_code in (302, 303), "فشل إنشاء مسير المرتبات")

    run = cur.execute(
        "SELECT id, status, posting_status, total_gross, total_deductions, total_net FROM hr_payroll_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert_true(run["status"] == "draft", "مسير الرواتب يجب أن يبدأ كمسودة")
    assert_true(run["posting_status"] == "unposted", "posting_status يجب أن يبدأ unposted")
    assert_true(round(float(run["total_gross"]), 2) == 5580.00, "إجمالي المستحقات غير صحيح")
    assert_true(round(float(run["total_deductions"]), 2) == 400.00, "إجمالي الاستقطاعات غير صحيح")
    assert_true(round(float(run["total_net"]), 2) == 5180.00, "صافي الراتب غير صحيح")

    payroll_line = cur.execute(
        """
        SELECT base_salary, allowance_amount, bonus_amount, overtime_amount, insurance_amount,
               tax_amount, loan_amount, penalty_amount, other_deduction, total_deductions, net_salary
        FROM hr_payroll_lines
        WHERE run_id=? AND employee_id=?
        """,
        (run["id"], first_employee["id"]),
    ).fetchone()
    assert_true(round(float(payroll_line["base_salary"]), 2) == 5000.00, "الراتب الأساسي غير صحيح")
    assert_true(round(float(payroll_line["total_deductions"]), 2) == 400.00, "إجمالي الاستقطاعات في السطر غير صحيح")
    assert_true(round(float(payroll_line["net_salary"]), 2) == 5180.00, "صافي السطر غير صحيح")

    payslip = client.get(f"/hr/payroll/{run['id']}/payslip/{first_employee['id']}")
    assert_true(payslip.status_code == 200, "شيت المرتب لا يعمل")
    payslip_html = payslip.get_data(as_text=True)
    assert_true("شيت مرتب" in payslip_html, "عنوان شيت المرتب غير ظاهر")
    assert_true("window.print()" in payslip_html, "زر الطباعة غير موجود")
    assert_true("EMP-001" in payslip_html, "كود الموظف غير ظاهر في شيت المرتب")

    post_run = client.post(f"/hr/payroll/{run['id']}/post", follow_redirects=False)
    assert_true(post_run.status_code in (302, 303), "فشل اعتماد مسير الرواتب")
    posted_run = cur.execute(
        "SELECT status, posting_status, journal_id FROM hr_payroll_runs WHERE id=?",
        (run["id"],),
    ).fetchone()
    assert_true(posted_run["status"] == "posted", "حالة المسير بعد الاعتماد يجب أن تكون posted")
    assert_true(posted_run["posting_status"] == "posted", "posting_status بعد الاعتماد غير صحيح")
    assert_true(posted_run["journal_id"] is not None, "journal_id لم يتم تخزينه")

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
        ("5110", "2310", 5000.00),
        ("5115", "2310", 580.00),
        ("2310", "2220", 150.00),
        ("2310", "2340", 50.00),
        ("2310", "2330", 200.00),
    }
    assert_true(expected_pairs.issubset(journal_pairs), "القيد المحاسبي الناتج عن الاعتماد غير مكتمل أو غير صحيح")
    total_posted = sum(row["amount"] for row in journal_rows)
    assert_true(total_posted == 5980.00, "إجمالي قيود الرواتب غير متوقع")

    repost = client.post(f"/hr/payroll/{run['id']}/post", follow_redirects=False)
    assert_true(repost.status_code in (302, 303), "فشل اختبار منع إعادة الترحيل")
    journal_count_after_repost = scalar(cur, "SELECT COUNT(*) FROM journal WHERE source_type='hr_payroll' AND source_id=?", (run["id"],))
    assert_true(journal_count_after_repost == len(journal_rows), "تم إنشاء قيود إضافية عند إعادة الترحيل")

    block_delete = client.post(f"/hr/employees/{first_employee['id']}/delete", follow_redirects=False)
    assert_true(block_delete.status_code in (302, 303), "فشل اختبار منع أرشفة موظف مرتبط بمسير مرحل")
    first_status_after_block = cur.execute("SELECT is_active FROM hr_employees WHERE id=?", (first_employee["id"],)).fetchone()
    assert_true(int(first_status_after_block["is_active"]) == 1, "يجب عدم أرشفة الموظف المرتبط بمرتبات مرحلة")

    conn.close()
    print(
        json.dumps(
            {
                "temp_db": str(temp_db),
                "run_id": run["id"],
                "journal_pairs": sorted(list(journal_pairs)),
                "first_employee_code": first_employee["employee_code"],
                "second_employee_code": second_employee["employee_code"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
