import sqlite3
from datetime import datetime

from flask import flash, redirect, render_template, request, session, url_for

from modules.hr.support import (
    ensure_hr_support_schema,
    ensure_payroll_accounts,
    generate_next_employee_code,
    get_department,
    payment_method_credit_code,
    payment_method_label,
)


def _connect(db):
    conn = db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    ensure_hr_support_schema(cur)
    conn.commit()
    return conn, cur


def _employee_department(cur, department_id):
    department = get_department(cur, department_id)
    return department["name"] if department else ""


def _employee_search_clause(query):
    if not query:
        return "", ()
    pattern = f"%{query}%"
    return (
        """
        AND (
            COALESCE(e.employee_code, '') LIKE ?
            OR COALESCE(e.name, '') LIKE ?
            OR COALESCE(d.name, e.department, '') LIKE ?
            OR COALESCE(e.job_title, '') LIKE ?
        )
        """,
        (pattern, pattern, pattern, pattern),
    )


def _build_payroll_line(employee):
    base_salary = float(employee["base_salary"] or 0)
    allowances = float(employee["allowances"] or 0)
    benefits = 0.0
    incentives = 0.0
    overtime = 0.0
    employee_insurance = float(employee["insurance_employee"] or 0)
    company_insurance = float(employee["insurance_company"] or 0)
    tax_amount = float(employee["tax"] or 0)
    advances = 0.0
    penalties = 0.0
    absence_deduction = 0.0
    tardiness_deduction = 0.0
    other_deductions = 0.0
    gross_salary = base_salary + allowances + benefits + incentives + overtime
    total_deductions = (
        employee_insurance
        + tax_amount
        + advances
        + penalties
        + absence_deduction
        + tardiness_deduction
        + other_deductions
    )
    net_salary = gross_salary - total_deductions
    return {
        "employee_id": employee["id"],
        "employee_code": employee["employee_code"] or employee["code"],
        "employee_name": employee["name"],
        "department_name": employee["department_name"] or employee["department"] or "",
        "job_title": employee["job_title"] or "",
        "base_salary": base_salary,
        "allowances": allowances,
        "benefits": benefits,
        "incentives": incentives,
        "overtime": overtime,
        "employee_insurance": employee_insurance,
        "company_insurance": company_insurance,
        "tax": tax_amount,
        "advances": advances,
        "penalties": penalties,
        "absence_deduction": absence_deduction,
        "tardiness_deduction": tardiness_deduction,
        "other_deductions": other_deductions,
        "gross_salary": gross_salary,
        "total_deductions": total_deductions,
        "net_salary": net_salary,
    }


def _load_run(cur, run_id):
    cur.execute(
        """
        SELECT id, period, date, total_gross, total_employee_deductions, total_company_insurance,
               total_net, status, posting_status, payment_method, journal_id, allowances_journal_id,
               tax_journal_id, insurance_journal_id, company_insurance_journal_id, deductions_journal_id,
               payment_journal_id, posted_at, posted_by, notes
        FROM payroll_runs
        WHERE id=?
        """,
        (run_id,),
    )
    return cur.fetchone()


def _post_payroll_run(cur, run, lines, create_auto_journal, mark_journal_source):
    period = run["period"]
    date_value = run["date"]
    payment_method = run["payment_method"] or "accrued"
    basic_total = sum(float(line["base_salary"] or 0) for line in lines)
    extras_total = sum(
        float(line["allowances"] or 0)
        + float(line["benefits"] or 0)
        + float(line["incentives"] or 0)
        + float(line["overtime"] or 0)
        for line in lines
    )
    employee_insurance_total = sum(float(line["insurance_employee"] or 0) for line in lines)
    company_insurance_total = sum(float(line["insurance_company"] or 0) for line in lines)
    tax_total = sum(float(line["tax"] or 0) for line in lines)
    other_deductions_total = sum(
        float(line["advances"] or 0)
        + float(line["penalties"] or 0)
        + float(line["absence_deduction"] or 0)
        + float(line["tardiness_deduction"] or 0)
        + float(line["other_deductions"] or 0)
        for line in lines
    )
    net_total = sum(float(line["net_salary"] or 0) for line in lines)

    journal_id = create_auto_journal(cur, date_value, f"إثبات الرواتب الأساسية {period}", "5110", "2310", basic_total) if basic_total > 0 else None
    allowances_journal_id = create_auto_journal(cur, date_value, f"إثبات البدلات والحوافز {period}", "5115", "2310", extras_total) if extras_total > 0 else None
    company_insurance_journal_id = create_auto_journal(cur, date_value, f"حصة الشركة في التأمينات {period}", "5170", "2220", company_insurance_total) if company_insurance_total > 0 else None
    insurance_journal_id = create_auto_journal(cur, date_value, f"استقطاع تأمينات الموظفين {period}", "2310", "2220", employee_insurance_total) if employee_insurance_total > 0 else None
    tax_journal_id = create_auto_journal(cur, date_value, f"استقطاع ضرائب الرواتب {period}", "2310", "2340", tax_total) if tax_total > 0 else None
    deductions_journal_id = create_auto_journal(cur, date_value, f"استقطاعات أخرى على الرواتب {period}", "2310", "2330", other_deductions_total) if other_deductions_total > 0 else None

    payment_journal_id = None
    status = "posted"
    if payment_method in {"cash", "bank"} and net_total > 0:
        payment_journal_id = create_auto_journal(
            cur,
            date_value,
            f"صرف صافي الرواتب {period}",
            "2310",
            payment_method_credit_code(payment_method),
            net_total,
        )
        status = "paid"

    mark_journal_source(
        cur,
        "payroll",
        run["id"],
        journal_id,
        allowances_journal_id,
        tax_journal_id,
        insurance_journal_id,
        company_insurance_journal_id,
        deductions_journal_id,
        payment_journal_id,
    )
    return {
        "journal_id": journal_id,
        "allowances_journal_id": allowances_journal_id,
        "tax_journal_id": tax_journal_id,
        "insurance_journal_id": insurance_journal_id,
        "company_insurance_journal_id": company_insurance_journal_id,
        "deductions_journal_id": deductions_journal_id,
        "payment_journal_id": payment_journal_id,
        "status": status,
        "posting_status": "posted",
    }


def build_employees_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    log_action = deps["log_action"]

    def employees():
        conn, cur = _connect(db)
        q = request.args.get("q", "").strip()

        if request.method == "POST":
            action = request.form.get("action", "add_employee")
            if action == "add_department":
                department_name = request.form.get("department_name", "").strip()
                if not department_name:
                    flash("اسم القسم مطلوب.", "danger")
                else:
                    try:
                        cur.execute("INSERT INTO departments(name) VALUES (?)", (department_name,))
                        conn.commit()
                        flash("تمت إضافة القسم بنجاح.", "success")
                    except sqlite3.IntegrityError:
                        flash("هذا القسم موجود بالفعل.", "warning")
            else:
                name = request.form.get("name", "").strip()
                department_id = int(parse_positive_amount(request.form.get("department_id")) or 0) or None
                job_title = request.form.get("job_title", "").strip()
                hire_date = request.form.get("hire_date", "").strip()
                base_salary = parse_positive_amount(request.form.get("base_salary"))
                allowances = parse_positive_amount(request.form.get("allowances"))
                insurance_employee = parse_positive_amount(request.form.get("insurance_employee"))
                insurance_company = parse_positive_amount(request.form.get("insurance_company"))
                tax_amount = parse_positive_amount(request.form.get("tax"))
                status = request.form.get("status", "active").strip() or "active"
                notes = request.form.get("notes", "").strip()
                employee_code = generate_next_employee_code(cur)
                department_name = _employee_department(cur, department_id)

                if not name:
                    flash("اسم الموظف مطلوب.", "danger")
                elif min(base_salary, allowances, insurance_employee, insurance_company, tax_amount) < 0:
                    flash("قيم الموظف لا يمكن أن تكون سالبة.", "danger")
                else:
                    try:
                        cur.execute(
                            """
                            INSERT INTO employees(
                                code, employee_code, name, department, department_id, job_title, hire_date,
                                base_salary, allowances, insurance_employee, insurance_company, tax, status, is_active, notes
                            )
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """,
                            (
                                employee_code,
                                employee_code,
                                name,
                                department_name,
                                department_id,
                                job_title,
                                hire_date,
                                base_salary,
                                allowances,
                                insurance_employee,
                                insurance_company,
                                tax_amount,
                                status,
                                1,
                                notes,
                            ),
                        )
                        employee_id = cur.lastrowid
                        log_action(cur, "create", "employee", employee_id, f"{name} / {employee_code}")
                        conn.commit()
                        flash(f"تمت إضافة الموظف بالكود {employee_code}.", "success")
                        return redirect(url_for("employees"))
                    except sqlite3.IntegrityError:
                        flash("تعذر إنشاء كود موظف فريد، حاول مرة أخرى.", "danger")

        where_clause, params = _employee_search_clause(q)
        cur.execute(
            f"""
            SELECT e.id, e.employee_code, e.code, e.name, e.department, e.department_id, e.job_title, e.hire_date,
                   e.base_salary, e.allowances, e.insurance_employee, e.insurance_company, e.tax,
                   e.status, e.is_active, e.notes, d.name AS department_name
            FROM employees e
            LEFT JOIN departments d ON d.id=e.department_id
            WHERE COALESCE(e.is_active, 1)=1
            {where_clause}
            ORDER BY e.id DESC
            """,
            params,
        )
        employee_rows = []
        for row in cur.fetchall():
            employee_rows.append(
                {
                    "id": row["id"],
                    "employee_code": row["employee_code"] or row["code"] or "-",
                    "name": row["name"],
                    "department_name": row["department_name"] or row["department"] or "-",
                    "job_title": row["job_title"] or "-",
                    "hire_date": row["hire_date"] or "-",
                    "base_salary": float(row["base_salary"] or 0),
                    "allowances": float(row["allowances"] or 0),
                    "insurance_employee": float(row["insurance_employee"] or 0),
                    "insurance_company": float(row["insurance_company"] or 0),
                    "tax": float(row["tax"] or 0),
                    "status": row["status"] or "active",
                }
            )

        cur.execute("SELECT id, name FROM departments WHERE status='active' ORDER BY name")
        departments = cur.fetchall()
        next_employee_code = generate_next_employee_code(cur)
        conn.close()
        return render_template(
            "hr/employees.html",
            employees=employee_rows,
            departments=departments,
            q=q,
            next_employee_code=next_employee_code,
        )

    return employees


def build_toggle_employee_view(deps):
    db = deps["db"]
    log_action = deps["log_action"]

    def toggle_employee(id):
        conn, cur = _connect(db)
        cur.execute("SELECT status, is_active FROM employees WHERE id=?", (id,))
        row = cur.fetchone()
        if not row or not row["is_active"]:
            conn.close()
            flash("الموظف غير موجود.", "danger")
            return redirect(url_for("employees"))
        new_status = "inactive" if row["status"] == "active" else "active"
        cur.execute("UPDATE employees SET status=? WHERE id=?", (new_status, id))
        log_action(cur, "update", "employee", id, f"status={new_status}")
        conn.commit()
        conn.close()
        flash("تم تحديث حالة الموظف.", "success")
        return redirect(url_for("employees"))

    return toggle_employee


def build_edit_employee_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    log_action = deps["log_action"]

    def edit_employee(id):
        conn, cur = _connect(db)
        cur.execute(
            """
            SELECT e.id, e.employee_code, e.code, e.name, e.department, e.department_id, e.job_title, e.hire_date,
                   e.base_salary, e.allowances, e.insurance_employee, e.insurance_company, e.tax,
                   e.notes, e.status, e.is_active
            FROM employees e
            WHERE e.id=?
            """,
            (id,),
        )
        employee = cur.fetchone()
        if not employee or not employee["is_active"]:
            conn.close()
            flash("الموظف غير موجود.", "danger")
            return redirect(url_for("employees"))

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            department_id = int(parse_positive_amount(request.form.get("department_id")) or 0) or None
            department_name = _employee_department(cur, department_id)
            job_title = request.form.get("job_title", "").strip()
            hire_date = request.form.get("hire_date", "").strip()
            base_salary = parse_positive_amount(request.form.get("base_salary"))
            allowances = parse_positive_amount(request.form.get("allowances"))
            insurance_employee = parse_positive_amount(request.form.get("insurance_employee"))
            insurance_company = parse_positive_amount(request.form.get("insurance_company"))
            tax_amount = parse_positive_amount(request.form.get("tax"))
            status = request.form.get("status", "active").strip() or "active"
            notes = request.form.get("notes", "").strip()

            if not name:
                flash("اسم الموظف مطلوب.", "danger")
            elif min(base_salary, allowances, insurance_employee, insurance_company, tax_amount) < 0:
                flash("القيم المالية لا يمكن أن تكون سالبة.", "danger")
            else:
                cur.execute(
                    """
                    UPDATE employees
                    SET name=?, department=?, department_id=?, job_title=?, hire_date=?, base_salary=?, allowances=?,
                        insurance_employee=?, insurance_company=?, tax=?, notes=?, status=?
                    WHERE id=?
                    """,
                    (
                        name,
                        department_name,
                        department_id,
                        job_title,
                        hire_date,
                        base_salary,
                        allowances,
                        insurance_employee,
                        insurance_company,
                        tax_amount,
                        notes,
                        status,
                        id,
                    ),
                )
                log_action(cur, "update", "employee", id, f"{name} / {employee['employee_code']}")
                conn.commit()
                conn.close()
                flash("تم تعديل الموظف.", "success")
                return redirect(url_for("employees"))

        cur.execute("SELECT id, name FROM departments WHERE status='active' ORDER BY name")
        departments = cur.fetchall()
        employee_view = {
            "id": employee["id"],
            "employee_code": employee["employee_code"] or employee["code"] or "",
            "name": employee["name"],
            "department_id": employee["department_id"],
            "job_title": employee["job_title"] or "",
            "hire_date": employee["hire_date"] or "",
            "base_salary": float(employee["base_salary"] or 0),
            "allowances": float(employee["allowances"] or 0),
            "insurance_employee": float(employee["insurance_employee"] or 0),
            "insurance_company": float(employee["insurance_company"] or 0),
            "tax": float(employee["tax"] or 0),
            "notes": employee["notes"] or "",
            "status": employee["status"] or "active",
        }
        conn.close()
        return render_template("edit_employee.html", employee=employee_view, departments=departments)

    return edit_employee


def build_delete_employee_view(deps):
    db = deps["db"]
    log_action = deps["log_action"]

    def delete_employee(id):
        conn, cur = _connect(db)
        cur.execute("SELECT name, employee_code, is_active FROM employees WHERE id=?", (id,))
        employee = cur.fetchone()
        if not employee or not employee["is_active"]:
            conn.close()
            flash("الموظف غير موجود.", "danger")
            return redirect(url_for("employees"))

        cur.execute("SELECT COUNT(*) FROM payroll_lines WHERE employee_id=?", (id,))
        payroll_links = cur.fetchone()[0]
        cur.execute(
            "UPDATE employees SET is_active=0, status='inactive' WHERE id=?",
            (id,),
        )
        log_action(cur, "archive", "employee", id, employee["name"])
        conn.commit()
        conn.close()
        if payroll_links:
            flash("تمت أرشفة الموظف بدلًا من الحذف لوجود حركات مرتبات مرتبطة به.", "warning")
        else:
            flash("تمت أرشفة الموظف بنجاح.", "success")
        return redirect(url_for("employees"))

    return delete_employee


def build_payroll_view(deps):
    db = deps["db"]
    ensure_open_period = deps["ensure_open_period"]
    log_action = deps["log_action"]

    def payroll():
        conn, cur = _connect(db)
        ensure_payroll_accounts(cur)
        conn.commit()

        if request.method == "POST":
            period = request.form.get("period", "").strip()
            date_value = request.form.get("date", "").strip()
            payment_method = request.form.get("payment_method", "accrued").strip() or "accrued"
            notes = request.form.get("notes", "").strip()

            cur.execute("SELECT id FROM payroll_runs WHERE period=? AND COALESCE(status,'') <> 'cancelled'", (period,))
            existing_run = cur.fetchone()
            cur.execute(
                """
                SELECT e.id, e.employee_code, e.code, e.name, e.department, d.name AS department_name, e.job_title,
                       e.base_salary, e.allowances, e.insurance_employee, e.insurance_company, e.tax
                FROM employees e
                LEFT JOIN departments d ON d.id=e.department_id
                WHERE COALESCE(e.is_active, 1)=1
                  AND COALESCE(e.status, 'active')='active'
                ORDER BY e.id
                """
            )
            employee_rows = cur.fetchall()

            if not period or not date_value:
                flash("الفترة والتاريخ مطلوبان.", "danger")
            elif existing_run:
                flash("يوجد كشف مرتبات لهذا الشهر بالفعل، وهذا يمنع ترحيل نفس الموظفين مرتين لنفس الفترة.", "danger")
            elif not employee_rows:
                flash("لا يوجد موظفون نشطون لإنشاء كشف المرتبات.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    conn.close()
                    flash(str(exc), "danger")
                    return redirect(url_for("payroll"))

                payroll_lines = []
                for employee in employee_rows:
                    line = _build_payroll_line(employee)
                    if line["net_salary"] < 0:
                        conn.close()
                        flash(f"استقطاعات الموظف {line['employee_name']} أكبر من إجمالي مستحقاته.", "danger")
                        return redirect(url_for("payroll"))
                    payroll_lines.append(line)

                total_gross = sum(line["gross_salary"] for line in payroll_lines)
                total_employee_deductions = sum(line["total_deductions"] for line in payroll_lines)
                total_company_insurance = sum(line["company_insurance"] for line in payroll_lines)
                total_net = sum(line["net_salary"] for line in payroll_lines)

                cur.execute(
                    """
                    INSERT INTO payroll_runs(
                        period, date, total_gross, total_employee_deductions, total_company_insurance, total_net,
                        status, posting_status, payment_method, notes
                    )
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        period,
                        date_value,
                        total_gross,
                        total_employee_deductions,
                        total_company_insurance,
                        total_net,
                        "draft",
                        "unposted",
                        payment_method,
                        notes,
                    ),
                )
                run_id = cur.lastrowid

                for line in payroll_lines:
                    cur.execute(
                        """
                        INSERT INTO payroll_lines(
                            run_id, employee_id, base_salary, allowances, benefits, incentives, overtime,
                            insurance_employee, insurance_company, tax, advances, penalties,
                            absence_deduction, tardiness_deduction, other_deductions,
                            gross_salary, total_deductions, net_salary, posting_status
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            run_id,
                            line["employee_id"],
                            line["base_salary"],
                            line["allowances"],
                            line["benefits"],
                            line["incentives"],
                            line["overtime"],
                            line["employee_insurance"],
                            line["company_insurance"],
                            line["tax"],
                            line["advances"],
                            line["penalties"],
                            line["absence_deduction"],
                            line["tardiness_deduction"],
                            line["other_deductions"],
                            line["gross_salary"],
                            line["total_deductions"],
                            line["net_salary"],
                            "unposted",
                        ),
                    )

                log_action(cur, "create", "payroll_run", run_id, f"period={period}; payment_method={payment_method}")
                conn.commit()
                conn.close()
                flash("تم إنشاء كشف المرتبات كمسودة آمنة وجاهز للاعتماد المحاسبي.", "success")
                return redirect(url_for("payroll_details", id=run_id))

        cur.execute(
            """
            SELECT id, period, date, total_gross, total_employee_deductions, total_company_insurance,
                   total_net, status, posting_status, payment_method, journal_id, payment_journal_id
            FROM payroll_runs
            ORDER BY id DESC
            """
        )
        runs = []
        for row in cur.fetchall():
            runs.append(
                {
                    "id": row["id"],
                    "period": row["period"],
                    "date": row["date"],
                    "total_gross": float(row["total_gross"] or 0),
                    "total_employee_deductions": float(row["total_employee_deductions"] or 0),
                    "total_company_insurance": float(row["total_company_insurance"] or 0),
                    "total_net": float(row["total_net"] or 0),
                    "status": row["status"] or "draft",
                    "posting_status": row["posting_status"] or "unposted",
                    "payment_method": row["payment_method"] or "accrued",
                    "journal_id": row["journal_id"],
                    "payment_journal_id": row["payment_journal_id"],
                }
            )
        cur.execute("SELECT COUNT(*) FROM employees WHERE COALESCE(is_active,1)=1 AND COALESCE(status,'active')='active'")
        active_count = cur.fetchone()[0]
        conn.close()
        return render_template("payroll.html", runs=runs, active_count=active_count, payment_method_label=payment_method_label)

    return payroll


def build_payroll_post_view(deps):
    db = deps["db"]
    ensure_open_period = deps["ensure_open_period"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]

    def payroll_post(id):
        conn, cur = _connect(db)
        ensure_payroll_accounts(cur)
        run = _load_run(cur, id)
        if not run:
            conn.close()
            flash("كشف المرتبات غير موجود.", "danger")
            return redirect(url_for("payroll"))
        if (run["posting_status"] or "unposted") == "posted":
            conn.close()
            flash("تم ترحيل هذا الكشف من قبل، ولا يمكن ترحيله مرتين.", "warning")
            return redirect(url_for("payroll_details", id=id))

        try:
            ensure_open_period(cur, run["date"])
        except ValueError as exc:
            conn.close()
            flash(str(exc), "danger")
            return redirect(url_for("payroll_details", id=id))

        cur.execute(
            """
            SELECT id, employee_id, base_salary, allowances, benefits, incentives, overtime, insurance_employee,
                   insurance_company, tax, advances, penalties, absence_deduction, tardiness_deduction,
                   other_deductions, gross_salary, total_deductions, net_salary
            FROM payroll_lines
            WHERE run_id=?
            ORDER BY id
            """,
            (id,),
        )
        lines = cur.fetchall()
        if not lines:
            conn.close()
            flash("لا توجد سطور مرتبات داخل هذا الكشف.", "danger")
            return redirect(url_for("payroll_details", id=id))

        postings = _post_payroll_run(cur, run, lines, create_auto_journal, mark_journal_source)
        cur.execute(
            """
            UPDATE payroll_runs
            SET status=?, posting_status=?, journal_id=?, allowances_journal_id=?, tax_journal_id=?,
                insurance_journal_id=?, company_insurance_journal_id=?, deductions_journal_id=?, payment_journal_id=?,
                posted_at=?, posted_by=?
            WHERE id=?
            """,
            (
                postings["status"],
                postings["posting_status"],
                postings["journal_id"],
                postings["allowances_journal_id"],
                postings["tax_journal_id"],
                postings["insurance_journal_id"],
                postings["company_insurance_journal_id"],
                postings["deductions_journal_id"],
                postings["payment_journal_id"],
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                session.get("username", "system"),
                id,
            ),
        )
        cur.execute("UPDATE payroll_lines SET posting_status='posted' WHERE run_id=?", (id,))
        log_action(cur, "post", "payroll_run", id, f"period={run['period']}")
        conn.commit()
        conn.close()
        rebuild_ledger()
        flash("تم اعتماد كشف المرتبات وترحيله محاسبيًا بنجاح.", "success")
        return redirect(url_for("payroll_details", id=id))

    return payroll_post


def build_payroll_details_view(deps):
    db = deps["db"]

    def payroll_details(id):
        conn, cur = _connect(db)
        run = _load_run(cur, id)
        if not run:
            conn.close()
            flash("كشف المرتبات غير موجود.", "danger")
            return redirect(url_for("payroll"))

        cur.execute(
            """
            SELECT l.id, l.employee_id, e.employee_code, e.code, e.name, e.department, d.name AS department_name,
                   e.job_title, l.base_salary, l.allowances, l.benefits, l.incentives, l.overtime,
                   l.insurance_employee, l.insurance_company, l.tax, l.advances, l.penalties,
                   l.absence_deduction, l.tardiness_deduction, l.other_deductions, l.gross_salary,
                   l.total_deductions, l.net_salary
            FROM payroll_lines l
            JOIN employees e ON e.id=l.employee_id
            LEFT JOIN departments d ON d.id=e.department_id
            WHERE l.run_id=?
            ORDER BY e.name
            """,
            (id,),
        )
        lines = []
        for row in cur.fetchall():
            lines.append(
                {
                    "id": row["id"],
                    "employee_id": row["employee_id"],
                    "employee_code": row["employee_code"] or row["code"] or "",
                    "employee_name": row["name"],
                    "department_name": row["department_name"] or row["department"] or "",
                    "job_title": row["job_title"] or "",
                    "base_salary": float(row["base_salary"] or 0),
                    "allowances": float(row["allowances"] or 0),
                    "benefits": float(row["benefits"] or 0),
                    "incentives": float(row["incentives"] or 0),
                    "overtime": float(row["overtime"] or 0),
                    "insurance_employee": float(row["insurance_employee"] or 0),
                    "insurance_company": float(row["insurance_company"] or 0),
                    "tax": float(row["tax"] or 0),
                    "advances": float(row["advances"] or 0),
                    "penalties": float(row["penalties"] or 0),
                    "absence_deduction": float(row["absence_deduction"] or 0),
                    "tardiness_deduction": float(row["tardiness_deduction"] or 0),
                    "other_deductions": float(row["other_deductions"] or 0),
                    "gross_salary": float(row["gross_salary"] or 0),
                    "total_deductions": float(row["total_deductions"] or 0),
                    "net_salary": float(row["net_salary"] or 0),
                }
            )

        run_view = {
            "id": run["id"],
            "period": run["period"],
            "date": run["date"],
            "total_gross": float(run["total_gross"] or 0),
            "total_employee_deductions": float(run["total_employee_deductions"] or 0),
            "total_company_insurance": float(run["total_company_insurance"] or 0),
            "total_net": float(run["total_net"] or 0),
            "status": run["status"] or "draft",
            "posting_status": run["posting_status"] or "unposted",
            "payment_method": run["payment_method"] or "accrued",
            "journal_id": run["journal_id"],
            "allowances_journal_id": run["allowances_journal_id"],
            "tax_journal_id": run["tax_journal_id"],
            "insurance_journal_id": run["insurance_journal_id"],
            "company_insurance_journal_id": run["company_insurance_journal_id"],
            "deductions_journal_id": run["deductions_journal_id"],
            "payment_journal_id": run["payment_journal_id"],
            "posted_at": run["posted_at"],
            "posted_by": run["posted_by"],
            "notes": run["notes"] or "",
        }
        conn.close()
        return render_template("payroll_details.html", run=run_view, lines=lines, payment_method_label=payment_method_label)

    return payroll_details


def build_payroll_payslip_view(deps):
    db = deps["db"]

    def payroll_payslip(run_id, employee_id):
        conn, cur = _connect(db)
        run = _load_run(cur, run_id)
        if not run:
            conn.close()
            flash("كشف المرتبات غير موجود.", "danger")
            return redirect(url_for("payroll"))

        cur.execute(
            """
            SELECT e.employee_code, e.code, e.name, e.department, d.name AS department_name, e.job_title,
                   l.base_salary, l.allowances, l.benefits, l.incentives, l.overtime, l.gross_salary,
                   l.insurance_employee, l.tax, l.advances, l.penalties, l.absence_deduction,
                   l.tardiness_deduction, l.other_deductions, l.total_deductions, l.net_salary
            FROM payroll_lines l
            JOIN employees e ON e.id=l.employee_id
            LEFT JOIN departments d ON d.id=e.department_id
            WHERE l.run_id=? AND l.employee_id=?
            """,
            (run_id, employee_id),
        )
        line = cur.fetchone()
        if not line:
            conn.close()
            flash("شيت المرتب غير موجود لهذا الموظف.", "danger")
            return redirect(url_for("payroll_details", id=run_id))

        payslip = {
            "employee_code": line["employee_code"] or line["code"] or "",
            "employee_name": line["name"],
            "department_name": line["department_name"] or line["department"] or "-",
            "job_title": line["job_title"] or "-",
            "period": run["period"],
            "base_salary": float(line["base_salary"] or 0),
            "allowances": float(line["allowances"] or 0),
            "benefits": float(line["benefits"] or 0),
            "incentives": float(line["incentives"] or 0),
            "overtime": float(line["overtime"] or 0),
            "gross_salary": float(line["gross_salary"] or 0),
            "insurance_employee": float(line["insurance_employee"] or 0),
            "tax": float(line["tax"] or 0),
            "advances": float(line["advances"] or 0),
            "penalties": float(line["penalties"] or 0),
            "absence_deduction": float(line["absence_deduction"] or 0),
            "tardiness_deduction": float(line["tardiness_deduction"] or 0),
            "other_deductions": float(line["other_deductions"] or 0),
            "total_deductions": float(line["total_deductions"] or 0),
            "net_salary": float(line["net_salary"] or 0),
        }
        conn.close()
        return render_template("payslip.html", payslip=payslip)

    return payroll_payslip
