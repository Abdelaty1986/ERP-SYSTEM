import sqlite3

from flask import flash, redirect, render_template, request, url_for


def build_employees_view(deps):
    db = deps["db"]
    parse_positive_amount = deps["parse_positive_amount"]
    log_action = deps["log_action"]

    def employees():
        conn = db()
        cur = conn.cursor()

        if request.method == "POST":
            code = request.form.get("code", "").strip() or None
            name = request.form.get("name", "").strip()
            department = request.form.get("department", "").strip()
            job_title = request.form.get("job_title", "").strip()
            hire_date = request.form.get("hire_date", "").strip()
            base_salary = parse_positive_amount(request.form.get("base_salary"))
            allowances = parse_positive_amount(request.form.get("allowances"))
            insurance_employee = parse_positive_amount(request.form.get("insurance_employee"))
            insurance_company = parse_positive_amount(request.form.get("insurance_company"))
            tax = parse_positive_amount(request.form.get("tax"))
            notes = request.form.get("notes", "").strip()

            if not name:
                flash("اسم الموظف مطلوب.", "danger")
            elif min(base_salary, allowances, insurance_employee, insurance_company, tax) < 0:
                flash("قيم الموظف لا يمكن أن تكون سالبة.", "danger")
            else:
                try:
                    cur.execute(
                        """
                        INSERT INTO employees(code,name,department,job_title,hire_date,base_salary,allowances,insurance_employee,insurance_company,tax,notes)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (code, name, department, job_title, hire_date, base_salary, allowances, insurance_employee, insurance_company, tax, notes),
                    )
                    employee_id = cur.lastrowid
                    log_action(cur, "create", "employee", employee_id, name)
                    conn.commit()
                    conn.close()
                    flash("تمت إضافة الموظف.", "success")
                    return redirect(url_for("employees"))
                except sqlite3.IntegrityError:
                    flash("كود الموظف مستخدم بالفعل.", "danger")

        cur.execute(
            """
            SELECT id,code,name,department,job_title,hire_date,base_salary,allowances,insurance_employee,insurance_company,tax,status
            FROM employees
            ORDER BY id DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("employees.html", rows=rows)

    return employees


def build_toggle_employee_view(deps):
    db = deps["db"]
    log_action = deps["log_action"]

    def toggle_employee(id):
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT status FROM employees WHERE id=?", (id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            flash("الموظف غير موجود.", "danger")
            return redirect(url_for("employees"))
        new_status = "inactive" if row[0] == "active" else "active"
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
        conn = db()
        cur = conn.cursor()
        cur.execute(
            "SELECT id,code,name,department,job_title,hire_date,base_salary,allowances,insurance_employee,insurance_company,tax,notes,status FROM employees WHERE id=?",
            (id,),
        )
        employee = cur.fetchone()
        if not employee:
            conn.close()
            flash("الموظف غير موجود.", "danger")
            return redirect(url_for("employees"))
        if request.method == "POST":
            data = [
                request.form.get("code", "").strip() or None,
                request.form.get("name", "").strip(),
                request.form.get("department", "").strip(),
                request.form.get("job_title", "").strip(),
                request.form.get("hire_date", "").strip(),
                parse_positive_amount(request.form.get("base_salary")),
                parse_positive_amount(request.form.get("allowances")),
                parse_positive_amount(request.form.get("insurance_employee")),
                parse_positive_amount(request.form.get("insurance_company")),
                parse_positive_amount(request.form.get("tax")),
                request.form.get("notes", "").strip(),
                id,
            ]
            if not data[1]:
                flash("اسم الموظف مطلوب.", "danger")
            else:
                try:
                    cur.execute(
                        """
                        UPDATE employees
                        SET code=?,name=?,department=?,job_title=?,hire_date=?,base_salary=?,allowances=?,insurance_employee=?,insurance_company=?,tax=?,notes=?
                        WHERE id=?
                        """,
                        data,
                    )
                    log_action(cur, "update", "employee", id, data[1])
                    conn.commit()
                    conn.close()
                    flash("تم تعديل الموظف.", "success")
                    return redirect(url_for("employees"))
                except sqlite3.IntegrityError:
                    flash("كود الموظف مستخدم بالفعل.", "danger")
        conn.close()
        return render_template("edit_employee.html", employee=employee)

    return edit_employee


def build_delete_employee_view(deps):
    db = deps["db"]
    log_action = deps["log_action"]

    def delete_employee(id):
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT name FROM employees WHERE id=?", (id,))
        employee = cur.fetchone()
        if not employee:
            conn.close()
            flash("الموظف غير موجود.", "danger")
            return redirect(url_for("employees"))
        cur.execute("SELECT COUNT(*) FROM payroll_lines WHERE employee_id=?", (id,))
        if cur.fetchone()[0]:
            conn.close()
            flash("لا يمكن حذف الموظف لوجود حركات مرتبات مرتبطة به.", "danger")
            return redirect(url_for("employees"))
        cur.execute("DELETE FROM employees WHERE id=?", (id,))
        log_action(cur, "delete", "employee", id, employee[0])
        conn.commit()
        conn.close()
        flash("تم حذف الموظف.", "success")
        return redirect(url_for("employees"))

    return delete_employee


def build_payroll_view(deps):
    db = deps["db"]
    ensure_open_period = deps["ensure_open_period"]
    create_auto_journal = deps["create_auto_journal"]
    mark_journal_source = deps["mark_journal_source"]
    log_action = deps["log_action"]
    rebuild_ledger = deps["rebuild_ledger"]

    def payroll():
        conn = db()
        cur = conn.cursor()

        if request.method == "POST":
            period = request.form.get("period", "").strip()
            date_value = request.form.get("date", "").strip()
            notes = request.form.get("notes", "").strip()

            cur.execute(
                """
                SELECT id,name,base_salary,allowances,insurance_employee,insurance_company,tax
                FROM employees
                WHERE status='active'
                ORDER BY id
                """
            )
            employee_rows = cur.fetchall()

            if not period or not date_value:
                flash("الفترة والتاريخ مطلوبان.", "danger")
            elif not employee_rows:
                flash("لا يوجد موظفون نشطون لإنشاء كشف المرتبات.", "danger")
            else:
                try:
                    ensure_open_period(cur, date_value)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    conn.close()
                    return redirect(url_for("payroll"))
                total_gross = 0
                total_employee_deductions = 0
                total_company_insurance = 0
                total_net = 0
                payroll_lines = []
                for employee_id, name, base_salary, allowances, insurance_employee, insurance_company, tax in employee_rows:
                    gross_salary = (base_salary or 0) + (allowances or 0)
                    deductions = (insurance_employee or 0) + (tax or 0)
                    net_salary = gross_salary - deductions
                    if net_salary < 0:
                        conn.close()
                        flash(f"استقطاعات الموظف {name} أكبر من إجمالي مستحقاته.", "danger")
                        return redirect(url_for("payroll"))
                    payroll_lines.append(
                        (
                            employee_id,
                            base_salary or 0,
                            allowances or 0,
                            insurance_employee or 0,
                            insurance_company or 0,
                            tax or 0,
                            0,
                            gross_salary,
                            net_salary,
                        )
                    )
                    total_gross += gross_salary
                    total_employee_deductions += deductions
                    total_company_insurance += insurance_company or 0
                    total_net += net_salary

                journal_id = create_auto_journal(cur, date_value, f"إثبات مرتبات {period}", "5110", "2310", total_net) if total_net > 0 else None
                tax_journal_id = create_auto_journal(cur, date_value, f"ضريبة كسب عمل مستحقة {period}", "5110", "2340", sum(line[5] for line in payroll_lines)) if sum(line[5] for line in payroll_lines) > 0 else None
                insurance_journal_id = create_auto_journal(cur, date_value, f"تأمينات عاملين مستحقة {period}", "5110", "2220", sum(line[3] for line in payroll_lines)) if sum(line[3] for line in payroll_lines) > 0 else None
                company_insurance_journal_id = create_auto_journal(cur, date_value, f"حصة الشركة في التأمينات {period}", "5170", "2220", total_company_insurance) if total_company_insurance > 0 else None

                cur.execute(
                    """
                    INSERT INTO payroll_runs(
                        period,date,total_gross,total_employee_deductions,total_company_insurance,total_net,
                        status,journal_id,tax_journal_id,insurance_journal_id,company_insurance_journal_id,notes
                    )
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        period,
                        date_value,
                        total_gross,
                        total_employee_deductions,
                        total_company_insurance,
                        total_net,
                        "posted",
                        journal_id,
                        tax_journal_id,
                        insurance_journal_id,
                        company_insurance_journal_id,
                        notes,
                    ),
                )
                run_id = cur.lastrowid
                mark_journal_source(cur, "payroll", run_id, journal_id, tax_journal_id, insurance_journal_id, company_insurance_journal_id)
                for line in payroll_lines:
                    cur.execute(
                        """
                        INSERT INTO payroll_lines(
                            run_id,employee_id,base_salary,allowances,insurance_employee,insurance_company,
                            tax,other_deductions,gross_salary,net_salary
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                        """,
                        (run_id, *line),
                    )
                log_action(cur, "create", "payroll_run", run_id, f"period={period}")
                conn.commit()
                conn.close()
                rebuild_ledger()
                flash("تم إنشاء وترحيل كشف المرتبات.", "success")
                return redirect(url_for("payroll"))

        cur.execute(
            """
            SELECT id,period,date,total_gross,total_employee_deductions,total_company_insurance,total_net,status
            FROM payroll_runs
            ORDER BY id DESC
            """
        )
        runs = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM employees WHERE status='active'")
        active_count = cur.fetchone()[0]
        conn.close()
        return render_template("payroll.html", runs=runs, active_count=active_count)

    return payroll


def build_payroll_details_view(deps):
    db = deps["db"]

    def payroll_details(id):
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id,period,date,total_gross,total_employee_deductions,total_company_insurance,total_net,status,notes
            FROM payroll_runs
            WHERE id=?
            """,
            (id,),
        )
        run = cur.fetchone()
        if not run:
            conn.close()
            flash("كشف المرتبات غير موجود.", "danger")
            return redirect(url_for("payroll"))
        cur.execute(
            """
            SELECT e.code,e.name,e.department,e.job_title,l.base_salary,l.allowances,l.insurance_employee,
                   l.insurance_company,l.tax,l.other_deductions,l.gross_salary,l.net_salary
            FROM payroll_lines l
            JOIN employees e ON e.id=l.employee_id
            WHERE l.run_id=?
            ORDER BY e.name
            """,
            (id,),
        )
        lines = cur.fetchall()
        conn.close()
        return render_template("payroll_details.html", run=run, lines=lines)

    return payroll_details
