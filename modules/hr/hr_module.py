# -*- coding: utf-8 -*-
"""
LedgerX HR Enterprise Blueprint
Employees + Attendance + Leaves + Payroll + Payslips + Accounting posting
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

hr_bp = Blueprint("hr", __name__, url_prefix="/hr")

DEFAULT_DEPARTMENTS = (
    "الإدارة",
    "الحسابات",
    "المبيعات",
    "المشتريات",
    "المخازن",
    "الموارد البشرية",
    "تكنولوجيا المعلومات",
    "خدمة العملاء",
    "التشغيل",
    "الصيانة",
    "التسويق",
    "الشئون القانونية",
    "الأمن",
    "النظافة",
)

DEFAULT_ACCOUNTS = (
    ("5110", "مصروف الرواتب والأجور", "مصروفات"),
    ("5115", "مصروف البدلات والحوافز والأجر الإضافي", "مصروفات"),
    ("2220", "التأمينات الاجتماعية المستحقة", "خصوم"),
    ("2330", "الاستقطاعات الأخرى المستحقة", "خصوم"),
    ("2340", "ضرائب كسب العمل المستحقة", "خصوم"),
    ("2310", "رواتب مستحقة", "خصوم"),
    ("1100", "الخزنة", "أصول"),
    ("1200", "البنك", "أصول"),
)

PAYROLL_ADJUSTMENT_LABELS = {
    "allowance": "بدل",
    "bonus": "علاوة",
    "incentive": "حافز",
    "overtime": "إضافي",
    "insurance": "تأمينات",
    "tax": "ضرائب",
    "loan": "سلف",
    "penalty": "جزاءات",
    "deduction": "استقطاع آخر",
}


DEFAULT_TAX_BRACKETS = (
    (40000.0, 0.00),
    (55000.0, 0.10),
    (70000.0, 0.15),
    (200000.0, 0.20),
    (400000.0, 0.225),
    (1200000.0, 0.25),
    (None, 0.275),
)


def _db_path() -> str:
    return current_app.config.get("DATABASE") or current_app.config.get("DB_PATH") or "database.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def _columns(cur: sqlite3.Cursor, table: str) -> set[str]:
    cur.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def _add_column_if_missing(cur: sqlite3.Cursor, table: str, column: str, ddl: str) -> None:
    if column not in _columns(cur, table):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _create_index_if_missing(cur: sqlite3.Cursor, name: str, table: str, columns: str, unique: bool = False) -> None:
    prefix = "CREATE UNIQUE INDEX IF NOT EXISTS" if unique else "CREATE INDEX IF NOT EXISTS"
    cur.execute(f"{prefix} {name} ON {table} ({columns})")


def _account_id(cur: sqlite3.Cursor, code: str) -> int | None:
    cur.execute("SELECT id FROM accounts WHERE code=?", (code,))
    row = cur.fetchone()
    return int(row[0]) if row else None


def _ensure_account(cur: sqlite3.Cursor, code: str, name: str, account_type: str) -> int:
    account_id = _account_id(cur, code)
    if account_id:
        return account_id
    cur.execute(
        "INSERT INTO accounts(code, name, type) VALUES (?, ?, ?)",
        (code, name, account_type),
    )
    return int(cur.lastrowid)


def _ensure_payroll_accounts(cur: sqlite3.Cursor) -> None:
    for code, name, account_type in DEFAULT_ACCOUNTS:
        _ensure_account(cur, code, name, account_type)


def _create_journal_by_codes(
    cur: sqlite3.Cursor,
    entry_date: str,
    description: str,
    debit_code: str,
    credit_code: str,
    amount: float,
    source_type: str = "hr_payroll",
    source_id: int | None = None,
) -> int | None:
    amount = round(float(amount or 0), 2)
    if amount <= 0:
        return None

    debit_id = _account_id(cur, debit_code)
    credit_id = _account_id(cur, credit_code)
    if not debit_id:
        raise ValueError(f"الحساب المدين بالكود {debit_code} غير موجود في شجرة الحسابات.")
    if not credit_id:
        raise ValueError(f"الحساب الدائن بالكود {credit_code} غير موجود في شجرة الحسابات.")

    cur.execute(
        """
        INSERT INTO journal(date, description, debit_account_id, credit_account_id, amount, status, source_type, source_id)
        VALUES (?, ?, ?, ?, ?, 'posted', ?, ?)
        """,
        (entry_date, description, debit_id, credit_id, amount, source_type, source_id),
    )
    journal_id = int(cur.lastrowid)

    try:
        cur.execute(
            "INSERT INTO ledger(account_id,date,description,debit,credit,journal_id) VALUES (?,?,?,?,?,?)",
            (debit_id, entry_date, description, amount, 0, journal_id),
        )
        cur.execute(
            "INSERT INTO ledger(account_id,date,description,debit,credit,journal_id) VALUES (?,?,?,?,?,?)",
            (credit_id, entry_date, description, 0, amount, journal_id),
        )
    except sqlite3.Error:
        pass

    return journal_id


def _minutes_between(t1: str | None, t2: str | None) -> int:
    if not t1 or not t2:
        return 0
    try:
        start = datetime.strptime(t1[:5], "%H:%M")
        end = datetime.strptime(t2[:5], "%H:%M")
        return max(0, int((end - start).total_seconds() // 60))
    except Exception:
        return 0


def _late_minutes(actual: str | None, expected: str | None) -> int:
    if not actual or not expected:
        return 0
    try:
        actual_dt = datetime.strptime(actual[:5], "%H:%M")
        expected_dt = datetime.strptime(expected[:5], "%H:%M")
        return max(0, int((actual_dt - expected_dt).total_seconds() // 60))
    except Exception:
        return 0


def _early_minutes(actual: str | None, expected: str | None) -> int:
    if not actual or not expected:
        return 0
    try:
        actual_dt = datetime.strptime(actual[:5], "%H:%M")
        expected_dt = datetime.strptime(expected[:5], "%H:%M")
        return max(0, int((expected_dt - actual_dt).total_seconds() // 60))
    except Exception:
        return 0


def _days_between(start_date: str, end_date: str) -> int:
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        return max(1, (end - start).days + 1)
    except Exception:
        return 1


def _scheduled_daily_minutes(employee: sqlite3.Row | None) -> int:
    minutes = _minutes_between(
        employee["work_start"] if employee else "09:00",
        employee["work_end"] if employee else "17:00",
    )
    return minutes if minutes > 0 else (8 * 60)


def _rule_float(rules: sqlite3.Row | None, key: str, default: float) -> float:
    if not rules:
        return default
    try:
        return float(rules[key] or default)
    except (TypeError, ValueError, KeyError):
        return default


def _hourly_rate(base_salary: float, employee: sqlite3.Row | None, rules: sqlite3.Row | None) -> float:
    monthly_work_days = max(1.0, _rule_float(rules, "monthly_work_days", 26.0))
    daily_hours = _scheduled_daily_minutes(employee) / 60
    monthly_hours = monthly_work_days * daily_hours
    if base_salary <= 0 or monthly_hours <= 0:
        return 0.0
    return base_salary / monthly_hours


def _progressive_tax(annual_taxable_income: float) -> float:
    taxable = max(0.0, float(annual_taxable_income or 0))
    tax_total = 0.0
    lower_limit = 0.0
    for upper_limit, rate in DEFAULT_TAX_BRACKETS:
        if upper_limit is None:
            taxable_slice = max(0.0, taxable - lower_limit)
        else:
            taxable_slice = max(0.0, min(taxable, upper_limit) - lower_limit)
        if taxable_slice > 0:
            tax_total += taxable_slice * rate
        if upper_limit is None or taxable <= upper_limit:
            break
        lower_limit = upper_limit
    return tax_total


def _employee_insurance_amount(base_salary: float, rules: sqlite3.Row | None) -> tuple[float, float]:
    if base_salary <= 0:
        return 0.0, 0.0
    minimum_salary = _rule_float(rules, "social_insurance_min_salary", 2700.0)
    maximum_salary = _rule_float(rules, "social_insurance_max_salary", 16700.0)
    insurance_rate = _rule_float(rules, "employee_insurance_rate", 0.11)
    insurance_base = max(minimum_salary, min(base_salary, maximum_salary))
    return round(insurance_base * insurance_rate, 2), round(insurance_base, 2)


def _employer_insurance_amount(insurance_base_salary: float, rules: sqlite3.Row | None) -> float:
    if insurance_base_salary <= 0:
        return 0.0
    employer_rate = _rule_float(rules, "employer_insurance_rate", 0.1875)
    return round(insurance_base_salary * employer_rate, 2)


def _monthly_salary_tax(
    gross_salary: float,
    attendance_deductions: float,
    employee_insurance_amount: float,
    rules: sqlite3.Row | None,
) -> float:
    annual_exemption = _rule_float(rules, "annual_salary_tax_exemption", 20000.0)
    monthly_taxable = max(0.0, gross_salary - attendance_deductions - employee_insurance_amount)
    annual_taxable = max(0.0, (monthly_taxable * 12) - annual_exemption)
    return round(_progressive_tax(annual_taxable) / 12, 2)


def _next_employee_code(cur: sqlite3.Cursor) -> str:
    cur.execute(
        """
        SELECT employee_code
        FROM hr_employees
        WHERE employee_code LIKE 'EMP-%'
        ORDER BY CAST(SUBSTR(employee_code, 5) AS INTEGER) DESC, id DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    last_number = 0
    if row and row["employee_code"]:
        try:
            last_number = int(str(row["employee_code"]).split("-")[-1])
        except (TypeError, ValueError):
            last_number = 0
    return f"EMP-{last_number + 1:03d}"


def _employee_status(is_active: int | None, status: str | None) -> str:
    if is_active == 0:
        return "inactive"
    return status or "active"


def _active_filter() -> str:
    return "COALESCE(e.is_active, CASE WHEN e.status='active' THEN 1 ELSE 0 END, 1)=1"


def init_hr_db() -> None:
    conn = sqlite3.connect(_db_path(), timeout=30)
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON")
    cur.execute("PRAGMA busy_timeout = 30000")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hr_departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hr_employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT UNIQUE,
            full_name TEXT NOT NULL,
            national_id TEXT,
            phone TEXT,
            email TEXT,
            department_id INTEGER,
            job_title TEXT,
            hire_date TEXT,
            base_salary REAL DEFAULT 0,
            work_start TEXT DEFAULT '09:00',
            work_end TEXT DEFAULT '17:00',
            annual_leave_balance REAL DEFAULT 21,
            status TEXT DEFAULT 'active',
            is_active INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(department_id) REFERENCES hr_departments(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hr_attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            work_date TEXT NOT NULL,
            check_in TEXT,
            check_out TEXT,
            late_minutes INTEGER DEFAULT 0,
            early_leave_minutes INTEGER DEFAULT 0,
            work_minutes INTEGER DEFAULT 0,
            overtime_minutes INTEGER DEFAULT 0,
            status TEXT DEFAULT 'present',
            source TEXT DEFAULT 'manual',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(employee_id, work_date),
            FOREIGN KEY(employee_id) REFERENCES hr_employees(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hr_leave_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            paid INTEGER DEFAULT 1,
            annual_deduct INTEGER DEFAULT 1,
            max_days REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hr_leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            leave_type_id INTEGER,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            days REAL DEFAULT 1,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            manager_note TEXT,
            approved_by TEXT,
            approved_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(employee_id) REFERENCES hr_employees(id),
            FOREIGN KEY(leave_type_id) REFERENCES hr_leave_types(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hr_payroll_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            late_deduction_per_min REAL DEFAULT 0,
            absent_day_deduction_rate REAL DEFAULT 1,
            overtime_rate_per_hour REAL DEFAULT 0,
            overtime_multiplier REAL DEFAULT 1.35,
            monthly_work_days REAL DEFAULT 26,
            employee_insurance_rate REAL DEFAULT 0.11,
            employer_insurance_rate REAL DEFAULT 0.1875,
            social_insurance_min_salary REAL DEFAULT 2700,
            social_insurance_max_salary REAL DEFAULT 16700,
            annual_salary_tax_exemption REAL DEFAULT 20000,
            salary_expense_account_code TEXT DEFAULT '5110',
            variable_compensation_account_code TEXT DEFAULT '5115',
            employer_insurance_expense_account_code TEXT DEFAULT '5116',
            salary_payable_account_code TEXT DEFAULT '2310',
            insurance_payable_account_code TEXT DEFAULT '2220',
            tax_payable_account_code TEXT DEFAULT '2340',
            deductions_payable_account_code TEXT DEFAULT '2330',
            cash_account_code TEXT DEFAULT '1100',
            bank_account_code TEXT DEFAULT '1200',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hr_salary_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            adjustment_month TEXT NOT NULL,
            adjustment_type TEXT NOT NULL DEFAULT 'allowance',
            title TEXT NOT NULL,
            amount REAL DEFAULT 0,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(employee_id) REFERENCES hr_employees(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hr_payroll_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payroll_month TEXT NOT NULL UNIQUE,
            run_date TEXT NOT NULL,
            status TEXT DEFAULT 'draft',
            posting_status TEXT DEFAULT 'unposted',
            payment_method TEXT DEFAULT 'accrued',
            total_gross REAL DEFAULT 0,
            total_deductions REAL DEFAULT 0,
            total_net REAL DEFAULT 0,
            journal_id INTEGER,
            payment_journal_id INTEGER,
            notes TEXT,
            posted_at TEXT,
            posted_by TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hr_payroll_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            base_salary REAL DEFAULT 0,
            hourly_rate REAL DEFAULT 0,
            scheduled_work_hours REAL DEFAULT 0,
            allowance_amount REAL DEFAULT 0,
            bonus_amount REAL DEFAULT 0,
            incentive_amount REAL DEFAULT 0,
            overtime_amount REAL DEFAULT 0,
            insurance_amount REAL DEFAULT 0,
            employer_insurance_amount REAL DEFAULT 0,
            insurance_base_salary REAL DEFAULT 0,
            tax_amount REAL DEFAULT 0,
            taxable_salary REAL DEFAULT 0,
            loan_amount REAL DEFAULT 0,
            penalty_amount REAL DEFAULT 0,
            late_deduction REAL DEFAULT 0,
            absence_deduction REAL DEFAULT 0,
            other_deduction REAL DEFAULT 0,
            gross_salary REAL DEFAULT 0,
            total_deductions REAL DEFAULT 0,
            net_salary REAL DEFAULT 0,
            present_days INTEGER DEFAULT 0,
            absent_days INTEGER DEFAULT 0,
            late_minutes INTEGER DEFAULT 0,
            early_minutes INTEGER DEFAULT 0,
            overtime_minutes INTEGER DEFAULT 0,
            posting_status TEXT DEFAULT 'unposted',
            journal_id INTEGER,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(run_id) REFERENCES hr_payroll_runs(id),
            FOREIGN KEY(employee_id) REFERENCES hr_employees(id)
        )
        """
    )

    for table, cols in {
        "hr_employees": [
            ("employee_code", "TEXT"),
            ("phone", "TEXT"),
            ("email", "TEXT"),
            ("national_id", "TEXT"),
            ("department_id", "INTEGER"),
            ("job_title", "TEXT"),
            ("hire_date", "TEXT"),
            ("base_salary", "REAL DEFAULT 0"),
            ("status", "TEXT DEFAULT 'active'"),
            ("is_active", "INTEGER NOT NULL DEFAULT 1"),
        ],
        "hr_payroll_rules": [
            ("overtime_multiplier", "REAL DEFAULT 1.35"),
            ("monthly_work_days", "REAL DEFAULT 26"),
            ("employee_insurance_rate", "REAL DEFAULT 0.11"),
            ("employer_insurance_rate", "REAL DEFAULT 0.1875"),
            ("social_insurance_min_salary", "REAL DEFAULT 2700"),
            ("social_insurance_max_salary", "REAL DEFAULT 16700"),
            ("annual_salary_tax_exemption", "REAL DEFAULT 20000"),
            ("salary_expense_account_code", "TEXT DEFAULT '5110'"),
            ("variable_compensation_account_code", "TEXT DEFAULT '5115'"),
            ("employer_insurance_expense_account_code", "TEXT DEFAULT '5116'"),
            ("salary_payable_account_code", "TEXT DEFAULT '2310'"),
            ("insurance_payable_account_code", "TEXT DEFAULT '2220'"),
            ("tax_payable_account_code", "TEXT DEFAULT '2340'"),
            ("deductions_payable_account_code", "TEXT DEFAULT '2330'"),
            ("cash_account_code", "TEXT DEFAULT '1100'"),
            ("bank_account_code", "TEXT DEFAULT '1200'"),
        ],
        "hr_payroll_runs": [
            ("posting_status", "TEXT DEFAULT 'unposted'"),
            ("payment_method", "TEXT DEFAULT 'accrued'"),
            ("posted_at", "TEXT"),
            ("posted_by", "TEXT"),
            ("journal_id", "INTEGER"),
            ("payment_journal_id", "INTEGER"),
            ("notes", "TEXT"),
            ("created_by", "TEXT"),
        ],
        "hr_payroll_lines": [
            ("hourly_rate", "REAL DEFAULT 0"),
            ("scheduled_work_hours", "REAL DEFAULT 0"),
            ("incentive_amount", "REAL DEFAULT 0"),
            ("insurance_amount", "REAL DEFAULT 0"),
            ("employer_insurance_amount", "REAL DEFAULT 0"),
            ("insurance_base_salary", "REAL DEFAULT 0"),
            ("tax_amount", "REAL DEFAULT 0"),
            ("taxable_salary", "REAL DEFAULT 0"),
            ("loan_amount", "REAL DEFAULT 0"),
            ("penalty_amount", "REAL DEFAULT 0"),
            ("posting_status", "TEXT DEFAULT 'unposted'"),
            ("journal_id", "INTEGER"),
            ("created_at", "TEXT"),
        ],
    }.items():
        for column, ddl in cols:
            _add_column_if_missing(cur, table, column, ddl)

    _create_index_if_missing(cur, "idx_hr_departments_name", "hr_departments", "name")
    _create_index_if_missing(cur, "idx_hr_employees_active", "hr_employees", "is_active, status")
    _create_index_if_missing(cur, "idx_hr_employees_department", "hr_employees", "department_id")
    _create_index_if_missing(cur, "idx_hr_payroll_runs_month", "hr_payroll_runs", "payroll_month", unique=True)
    _create_index_if_missing(cur, "idx_hr_payroll_lines_run_employee", "hr_payroll_lines", "run_id, employee_id", unique=True)
    _create_index_if_missing(cur, "idx_hr_salary_adjustments_employee_month", "hr_salary_adjustments", "employee_id, adjustment_month")

    cur.execute(
        """
        UPDATE hr_employees
        SET is_active = CASE
            WHEN status = 'inactive' THEN 0
            ELSE 1
        END
        WHERE is_active IS NULL OR is_active NOT IN (0,1)
        """
    )

    for name in DEFAULT_DEPARTMENTS:
        cur.execute("INSERT OR IGNORE INTO hr_departments(name) VALUES (?)", (name,))

    for row in [("سنوية", 1, 1), ("مرضية", 1, 0), ("بدون أجر", 0, 0), ("عارضة", 1, 1)]:
        cur.execute(
            "INSERT OR IGNORE INTO hr_leave_types(name, paid, annual_deduct) VALUES (?, ?, ?)",
            row,
        )

    cur.execute("SELECT COUNT(*) FROM hr_payroll_rules")
    if int(cur.fetchone()[0] or 0) == 0:
        cur.execute(
            """
            INSERT INTO hr_payroll_rules(
                late_deduction_per_min,
                absent_day_deduction_rate,
                overtime_rate_per_hour,
                overtime_multiplier,
                monthly_work_days,
                employee_insurance_rate,
                employer_insurance_rate,
                social_insurance_min_salary,
                social_insurance_max_salary,
                annual_salary_tax_exemption,
                salary_expense_account_code,
                variable_compensation_account_code,
                employer_insurance_expense_account_code,
                salary_payable_account_code,
                insurance_payable_account_code,
                tax_payable_account_code,
                deductions_payable_account_code,
                cash_account_code,
                bank_account_code
            )
            VALUES (0, 1, 0, 1.35, 26, 0.11, 0.1875, 2700, 16700, 20000, '5110', '5115', '5116', '2310', '2220', '2340', '2330', '1100', '1200')
            """
        )
    else:
        cur.execute(
            """
            UPDATE hr_payroll_rules
            SET
                salary_expense_account_code = CASE
                    WHEN salary_expense_account_code IS NULL OR salary_expense_account_code IN ('', '6200') THEN '5110'
                    ELSE salary_expense_account_code
                END,
                variable_compensation_account_code = CASE
                    WHEN variable_compensation_account_code IS NULL OR variable_compensation_account_code = '' THEN '5115'
                    ELSE variable_compensation_account_code
                END,
                employer_insurance_expense_account_code = CASE
                    WHEN employer_insurance_expense_account_code IS NULL OR employer_insurance_expense_account_code = '' THEN '5116'
                    ELSE employer_insurance_expense_account_code
                END,
                salary_payable_account_code = CASE
                    WHEN salary_payable_account_code IS NULL OR salary_payable_account_code IN ('', '2300') THEN '2310'
                    ELSE salary_payable_account_code
                END,
                insurance_payable_account_code = CASE
                    WHEN insurance_payable_account_code IS NULL OR insurance_payable_account_code = '' THEN '2220'
                    ELSE insurance_payable_account_code
                END,
                tax_payable_account_code = CASE
                    WHEN tax_payable_account_code IS NULL OR tax_payable_account_code = '' THEN '2340'
                    ELSE tax_payable_account_code
                END,
                deductions_payable_account_code = CASE
                    WHEN deductions_payable_account_code IS NULL OR deductions_payable_account_code = '' THEN '2330'
                    ELSE deductions_payable_account_code
                END,
                cash_account_code = CASE
                    WHEN cash_account_code IS NULL OR cash_account_code = '' THEN '1100'
                    ELSE cash_account_code
                END,
                bank_account_code = CASE
                    WHEN bank_account_code IS NULL OR bank_account_code = '' THEN '1200'
                    ELSE bank_account_code
                END,
                overtime_multiplier = CASE
                    WHEN overtime_multiplier IS NULL OR overtime_multiplier <= 0 THEN 1.35
                    ELSE overtime_multiplier
                END,
                monthly_work_days = CASE
                    WHEN monthly_work_days IS NULL OR monthly_work_days <= 0 THEN 26
                    ELSE monthly_work_days
                END,
                employee_insurance_rate = CASE
                    WHEN employee_insurance_rate IS NULL OR employee_insurance_rate <= 0 THEN 0.11
                    ELSE employee_insurance_rate
                END,
                employer_insurance_rate = CASE
                    WHEN employer_insurance_rate IS NULL OR employer_insurance_rate <= 0 THEN 0.1875
                    ELSE employer_insurance_rate
                END,
                social_insurance_min_salary = CASE
                    WHEN social_insurance_min_salary IS NULL OR social_insurance_min_salary <= 0 THEN 2700
                    ELSE social_insurance_min_salary
                END,
                social_insurance_max_salary = CASE
                    WHEN social_insurance_max_salary IS NULL OR social_insurance_max_salary <= 0 THEN 16700
                    ELSE social_insurance_max_salary
                END,
                annual_salary_tax_exemption = CASE
                    WHEN annual_salary_tax_exemption IS NULL OR annual_salary_tax_exemption < 0 THEN 20000
                    ELSE annual_salary_tax_exemption
                END
            """
        )

    _ensure_payroll_accounts(cur)
    _ensure_account(cur, "5116", "مساهمة الشركة في التأمينات الاجتماعية", "مصروفات")
    conn.commit()
    conn.close()


def _get_departments(cur: sqlite3.Cursor):
    return cur.execute("SELECT * FROM hr_departments ORDER BY name").fetchall()


def _get_employee(cur: sqlite3.Cursor, employee_id: int):
    return cur.execute(
        f"""
        SELECT
            e.*,
            d.name AS department_name,
            CASE
                WHEN COALESCE(e.is_active, 1) = 1 AND COALESCE(e.status, 'active') = 'active' THEN 'active'
                ELSE 'inactive'
            END AS normalized_status
        FROM hr_employees e
        LEFT JOIN hr_departments d ON d.id = e.department_id
        WHERE e.id = ?
        """,
        (employee_id,),
    ).fetchone()


@hr_bp.before_request
def _ensure_db():
    init_hr_db()
    if "user_id" not in session:
        return redirect(url_for("login"))


@hr_bp.route("/")
def dashboard():
    conn = get_db()
    cur = conn.cursor()
    today = date.today().isoformat()
    stats = {
        "employees": int(cur.execute(f"SELECT COUNT(*) FROM hr_employees e WHERE {_active_filter()}").fetchone()[0] or 0),
        "present_today": int(cur.execute("SELECT COUNT(*) FROM hr_attendance WHERE work_date=? AND status='present'", (today,)).fetchone()[0] or 0),
        "late_today": int(cur.execute("SELECT COUNT(*) FROM hr_attendance WHERE work_date=? AND late_minutes>0", (today,)).fetchone()[0] or 0),
        "pending_leaves": int(cur.execute("SELECT COUNT(*) FROM hr_leaves WHERE status='pending'").fetchone()[0] or 0),
        "payroll_draft": int(cur.execute("SELECT COUNT(*) FROM hr_payroll_runs WHERE status='draft'").fetchone()[0] or 0),
        "payroll_posted": int(cur.execute("SELECT COUNT(*) FROM hr_payroll_runs WHERE status IN ('posted','paid')").fetchone()[0] or 0),
    }
    recent_attendance = cur.execute(
        """
        SELECT a.*, e.full_name
        FROM hr_attendance a
        JOIN hr_employees e ON e.id = a.employee_id
        ORDER BY a.work_date DESC, a.id DESC
        LIMIT 10
        """
    ).fetchall()
    pending_leaves = cur.execute(
        """
        SELECT l.*, e.full_name, t.name AS leave_type
        FROM hr_leaves l
        JOIN hr_employees e ON e.id = l.employee_id
        LEFT JOIN hr_leave_types t ON t.id = l.leave_type_id
        WHERE l.status='pending'
        ORDER BY l.id DESC
        LIMIT 8
        """
    ).fetchall()
    recent_payroll = cur.execute("SELECT * FROM hr_payroll_runs ORDER BY id DESC LIMIT 5").fetchall()
    conn.close()
    return render_template(
        "hr/dashboard.html",
        stats=stats,
        recent_attendance=recent_attendance,
        pending_leaves=pending_leaves,
        recent_payroll=recent_payroll,
    )


@hr_bp.route("/employees")
def employees():
    q = request.args.get("q", "").strip()
    conn = get_db()
    cur = conn.cursor()
    params: tuple[str, ...] = ()
    where = ""
    if q:
        like = f"%{q}%"
        where = """
        WHERE
            e.full_name LIKE ?
            OR COALESCE(e.employee_code, '') LIKE ?
            OR COALESCE(d.name, '') LIKE ?
            OR COALESCE(e.job_title, '') LIKE ?
            OR COALESCE(e.phone, '') LIKE ?
        """
        params = (like, like, like, like, like)
    rows = cur.execute(
        f"""
        SELECT
            e.*,
            d.name AS department_name,
            CASE
                WHEN COALESCE(e.is_active, 1) = 1 AND COALESCE(e.status, 'active') = 'active' THEN 'active'
                ELSE 'inactive'
            END AS normalized_status
        FROM hr_employees e
        LEFT JOIN hr_departments d ON d.id = e.department_id
        {where}
        ORDER BY e.id DESC
        """,
        params,
    ).fetchall()
    departments = _get_departments(cur)
    next_employee_code = _next_employee_code(cur)
    conn.close()
    return render_template(
        "hr/employees.html",
        employees=rows,
        departments=departments,
        next_employee_code=next_employee_code,
        q=q,
    )


@hr_bp.route("/employees/add", methods=["POST"])
def add_employee():
    conn = get_db()
    cur = conn.cursor()

    department_name = (request.form.get("department_name") or "").strip()
    if department_name:
        cur.execute("INSERT OR IGNORE INTO hr_departments(name) VALUES (?)", (department_name,))

    department_id = request.form.get("department_id") or None
    if not department_id and department_name:
        department_row = cur.execute("SELECT id FROM hr_departments WHERE name=?", (department_name,)).fetchone()
        department_id = department_row["id"] if department_row else None

    employee_code = _next_employee_code(cur)
    for _ in range(5):
        try:
            cur.execute(
                """
                INSERT INTO hr_employees(
                    employee_code, full_name, national_id, phone, email, department_id,
                    job_title, hire_date, base_salary, work_start, work_end,
                    annual_leave_balance, status, is_active, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    employee_code,
                    request.form.get("full_name"),
                    request.form.get("national_id"),
                    request.form.get("phone"),
                    request.form.get("email"),
                    department_id,
                    request.form.get("job_title"),
                    request.form.get("hire_date"),
                    float(request.form.get("base_salary") or 0),
                    request.form.get("work_start") or "09:00",
                    request.form.get("work_end") or "17:00",
                    float(request.form.get("annual_leave_balance") or 21),
                    "active" if (request.form.get("status") or "active") == "active" else "inactive",
                    1 if (request.form.get("status") or "active") == "active" else 0,
                    request.form.get("notes"),
                ),
            )
            conn.commit()
            flash("تمت إضافة الموظف بنجاح.", "success")
            conn.close()
            return redirect(url_for("hr.employees"))
        except sqlite3.IntegrityError:
            employee_code = _next_employee_code(cur)

    conn.rollback()
    conn.close()
    flash("تعذر توليد كود موظف فريد. حاول مرة أخرى.", "danger")
    return redirect(url_for("hr.employees"))


@hr_bp.route("/employees/<int:employee_id>")
def employee_view(employee_id: int):
    conn = get_db()
    cur = conn.cursor()
    employee = _get_employee(cur, employee_id)
    if not employee:
        conn.close()
        flash("الموظف غير موجود.", "danger")
        return redirect(url_for("hr.employees"))

    payroll_summary = cur.execute(
        """
        SELECT COUNT(*) AS runs_count, COALESCE(MAX(r.payroll_month), '-') AS last_month
        FROM hr_payroll_lines l
        JOIN hr_payroll_runs r ON r.id = l.run_id
        WHERE l.employee_id = ?
        """,
        (employee_id,),
    ).fetchone()
    conn.close()
    return render_template("hr/employee_view.html", employee=employee, payroll_summary=payroll_summary)


@hr_bp.route("/employees/<int:employee_id>/edit", methods=["GET", "POST"])
def employee_edit(employee_id: int):
    conn = get_db()
    cur = conn.cursor()
    employee = _get_employee(cur, employee_id)
    if not employee:
        conn.close()
        flash("الموظف غير موجود.", "danger")
        return redirect(url_for("hr.employees"))

    if request.method == "POST":
        department_name = (request.form.get("department_name") or "").strip()
        if department_name:
            cur.execute("INSERT OR IGNORE INTO hr_departments(name) VALUES (?)", (department_name,))

        department_id = request.form.get("department_id") or None
        if not department_id and department_name:
            department_row = cur.execute("SELECT id FROM hr_departments WHERE name=?", (department_name,)).fetchone()
            department_id = department_row["id"] if department_row else None

        status = "active" if (request.form.get("status") or "active") == "active" else "inactive"
        cur.execute(
            """
            UPDATE hr_employees
            SET full_name=?, national_id=?, phone=?, email=?, department_id=?,
                job_title=?, hire_date=?, base_salary=?, work_start=?, work_end=?,
                annual_leave_balance=?, status=?, is_active=?, notes=?
            WHERE id=?
            """,
            (
                request.form.get("full_name"),
                request.form.get("national_id"),
                request.form.get("phone"),
                request.form.get("email"),
                department_id,
                request.form.get("job_title"),
                request.form.get("hire_date"),
                float(request.form.get("base_salary") or 0),
                request.form.get("work_start") or "09:00",
                request.form.get("work_end") or "17:00",
                float(request.form.get("annual_leave_balance") or 21),
                status,
                1 if status == "active" else 0,
                request.form.get("notes"),
                employee_id,
            ),
        )
        conn.commit()
        conn.close()
        flash("تم تحديث بيانات الموظف.", "success")
        return redirect(url_for("hr.employee_view", employee_id=employee_id))

    departments = _get_departments(cur)
    conn.close()
    return render_template("hr/employee_form.html", employee=employee, departments=departments)


@hr_bp.route("/employees/<int:employee_id>/delete", methods=["POST"])
def employee_delete(employee_id: int):
    conn = get_db()
    cur = conn.cursor()
    employee = _get_employee(cur, employee_id)
    if not employee:
        conn.close()
        flash("الموظف غير موجود.", "danger")
        return redirect(url_for("hr.employees"))

    linked_posted = cur.execute(
        """
        SELECT COUNT(*)
        FROM hr_payroll_lines l
        JOIN hr_payroll_runs r ON r.id = l.run_id
        WHERE l.employee_id = ? AND r.status IN ('posted', 'paid')
        """,
        (employee_id,),
    ).fetchone()[0]
    if int(linked_posted or 0) > 0:
        conn.close()
        flash("لا يمكن أرشفة الموظف لأنه مرتبط بمرتبات مرحلة أو مدفوعة.", "warning")
        return redirect(url_for("hr.employees"))

    cur.execute(
        "UPDATE hr_employees SET is_active=0, status='inactive' WHERE id=?",
        (employee_id,),
    )
    conn.commit()
    conn.close()
    flash("تمت أرشفة الموظف بنجاح.", "success")
    return redirect(url_for("hr.employees"))


@hr_bp.route("/attendance", methods=["GET", "POST"])
def attendance():
    conn = get_db()
    cur = conn.cursor()
    if request.method == "POST":
        employee_id = request.form.get("employee_id")
        work_date = request.form.get("work_date") or date.today().isoformat()
        check_in = request.form.get("check_in")
        check_out = request.form.get("check_out")
        notes = request.form.get("notes")
        emp = cur.execute("SELECT * FROM hr_employees WHERE id=?", (employee_id,)).fetchone()
        late = _late_minutes(check_in, emp["work_start"] if emp else "09:00")
        early = _early_minutes(check_out, emp["work_end"] if emp else "17:00")
        work_minutes = _minutes_between(check_in, check_out)
        expected = _minutes_between(emp["work_start"], emp["work_end"]) if emp else 480
        overtime = max(0, work_minutes - expected)
        cur.execute(
            """
            INSERT INTO hr_attendance(
                employee_id, work_date, check_in, check_out, late_minutes,
                early_leave_minutes, work_minutes, overtime_minutes, status, source, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'present', 'manual', ?)
            ON CONFLICT(employee_id, work_date) DO UPDATE SET
                check_in=excluded.check_in,
                check_out=excluded.check_out,
                late_minutes=excluded.late_minutes,
                early_leave_minutes=excluded.early_leave_minutes,
                work_minutes=excluded.work_minutes,
                overtime_minutes=excluded.overtime_minutes,
                status='present',
                notes=excluded.notes
            """,
            (employee_id, work_date, check_in, check_out, late, early, work_minutes, overtime, notes),
        )
        conn.commit()
        flash("تم حفظ الحضور والانصراف.", "success")
        return redirect(url_for("hr.attendance", d=work_date))

    selected_date = request.args.get("d") or date.today().isoformat()
    employees = cur.execute(
        f"SELECT * FROM hr_employees e WHERE {_active_filter()} ORDER BY full_name"
    ).fetchall()
    rows = cur.execute(
        """
        SELECT a.*, e.full_name, e.employee_code
        FROM hr_attendance a
        JOIN hr_employees e ON e.id = a.employee_id
        WHERE a.work_date=?
        ORDER BY e.full_name
        """,
        (selected_date,),
    ).fetchall()
    conn.close()
    return render_template("hr/attendance.html", employees=employees, rows=rows, selected_date=selected_date)


@hr_bp.route("/attendance/mark-absent", methods=["POST"])
def mark_absent():
    conn = get_db()
    cur = conn.cursor()
    work_date = request.form.get("work_date") or date.today().isoformat()
    cur.execute(f"SELECT id FROM hr_employees e WHERE {_active_filter()}")
    ids = [row[0] for row in cur.fetchall()]
    for employee_id in ids:
        cur.execute(
            """
            INSERT OR IGNORE INTO hr_attendance(employee_id, work_date, status, source, notes)
            VALUES (?, ?, 'absent', 'system', 'تم تسجيله غائب تلقائياً')
            """,
            (employee_id, work_date),
        )
    conn.commit()
    conn.close()
    flash("تم تسجيل الغياب للموظفين غير المسجلين.", "success")
    return redirect(url_for("hr.attendance", d=work_date))


@hr_bp.route("/leaves", methods=["GET", "POST"])
def leaves():
    conn = get_db()
    cur = conn.cursor()
    if request.method == "POST":
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        days = _days_between(start_date, end_date)
        cur.execute(
            """
            INSERT INTO hr_leaves(employee_id, leave_type_id, start_date, end_date, days, reason, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                request.form.get("employee_id"),
                request.form.get("leave_type_id"),
                start_date,
                end_date,
                days,
                request.form.get("reason"),
            ),
        )
        conn.commit()
        flash("تم إرسال طلب الإجازة للموافقة.", "success")
        return redirect(url_for("hr.leaves"))

    employees = cur.execute(f"SELECT * FROM hr_employees e WHERE {_active_filter()} ORDER BY full_name").fetchall()
    leave_types = cur.execute("SELECT * FROM hr_leave_types ORDER BY name").fetchall()
    rows = cur.execute(
        """
        SELECT l.*, e.full_name, t.name AS leave_type, t.annual_deduct
        FROM hr_leaves l
        JOIN hr_employees e ON e.id = l.employee_id
        LEFT JOIN hr_leave_types t ON t.id = l.leave_type_id
        ORDER BY l.id DESC
        """
    ).fetchall()
    conn.close()
    return render_template("hr/leaves.html", employees=employees, leave_types=leave_types, rows=rows)


@hr_bp.route("/leaves/<int:leave_id>/<action>", methods=["POST"])
def leave_action(leave_id: int, action: str):
    if action not in {"approve", "reject"}:
        flash("إجراء غير صحيح.", "danger")
        return redirect(url_for("hr.leaves"))

    conn = get_db()
    cur = conn.cursor()
    leave = cur.execute(
        """
        SELECT l.*, t.annual_deduct
        FROM hr_leaves l
        LEFT JOIN hr_leave_types t ON t.id = l.leave_type_id
        WHERE l.id=?
        """,
        (leave_id,),
    ).fetchone()
    status = "approved" if action == "approve" else "rejected"
    approved_by = session.get("username") or session.get("user") or "admin"
    cur.execute(
        "UPDATE hr_leaves SET status=?, manager_note=?, approved_by=?, approved_at=? WHERE id=?",
        (status, request.form.get("manager_note"), approved_by, datetime.now().strftime("%Y-%m-%d %H:%M"), leave_id),
    )
    if leave and status == "approved" and leave["annual_deduct"]:
        cur.execute(
            "UPDATE hr_employees SET annual_leave_balance = annual_leave_balance - ? WHERE id=?",
            (leave["days"], leave["employee_id"]),
        )
    conn.commit()
    conn.close()
    flash("تم تحديث حالة الإجازة.", "success")
    return redirect(url_for("hr.leaves"))


@hr_bp.route("/reports")
def reports():
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    conn = get_db()
    cur = conn.cursor()
    rows = cur.execute(
        f"""
        SELECT
            e.id,
            e.full_name,
            e.employee_code,
            e.base_salary,
            COUNT(CASE WHEN a.status='present' THEN 1 END) AS present_days,
            COUNT(CASE WHEN a.status='absent' THEN 1 END) AS absent_days,
            COALESCE(SUM(a.late_minutes),0) AS late_minutes,
            COALESCE(SUM(a.early_leave_minutes),0) AS early_minutes,
            COALESCE(SUM(a.overtime_minutes),0) AS overtime_minutes
        FROM hr_employees e
        LEFT JOIN hr_attendance a ON a.employee_id=e.id AND substr(a.work_date,1,7)=?
        WHERE {_active_filter()}
        GROUP BY e.id
        ORDER BY e.full_name
        """,
        (month,),
    ).fetchall()
    conn.close()
    return render_template("hr/reports.html", rows=rows, month=month)


@hr_bp.route("/payroll", methods=["GET", "POST"])
def payroll():
    conn = get_db()
    cur = conn.cursor()
    if request.method == "POST":
        form_action = request.form.get("form_action") or "add_adjustment"
        if form_action == "update_rules":
            rules_row = cur.execute("SELECT id FROM hr_payroll_rules ORDER BY id DESC LIMIT 1").fetchone()
            if rules_row:
                cur.execute(
                    """
                    UPDATE hr_payroll_rules
                    SET
                        late_deduction_per_min=?,
                        absent_day_deduction_rate=?,
                        overtime_rate_per_hour=?,
                        overtime_multiplier=?,
                        monthly_work_days=?,
                        employee_insurance_rate=?,
                        employer_insurance_rate=?,
                        social_insurance_min_salary=?,
                        social_insurance_max_salary=?,
                        annual_salary_tax_exemption=?,
                        salary_expense_account_code=?,
                        variable_compensation_account_code=?,
                        employer_insurance_expense_account_code=?,
                        salary_payable_account_code=?,
                        insurance_payable_account_code=?,
                        tax_payable_account_code=?,
                        deductions_payable_account_code=?,
                        cash_account_code=?,
                        bank_account_code=?
                    WHERE id=?
                    """,
                    (
                        float(request.form.get("late_deduction_per_min") or 0),
                        float(request.form.get("absent_day_deduction_rate") or 1),
                        float(request.form.get("overtime_rate_per_hour") or 0),
                        float(request.form.get("overtime_multiplier") or 1.35),
                        float(request.form.get("monthly_work_days") or 26),
                        float(request.form.get("employee_insurance_rate") or 0.11),
                        float(request.form.get("employer_insurance_rate") or 0.1875),
                        float(request.form.get("social_insurance_min_salary") or 2700),
                        float(request.form.get("social_insurance_max_salary") or 16700),
                        float(request.form.get("annual_salary_tax_exemption") or 20000),
                        request.form.get("salary_expense_account_code") or "5110",
                        request.form.get("variable_compensation_account_code") or "5115",
                        request.form.get("employer_insurance_expense_account_code") or "5116",
                        request.form.get("salary_payable_account_code") or "2310",
                        request.form.get("insurance_payable_account_code") or "2220",
                        request.form.get("tax_payable_account_code") or "2340",
                        request.form.get("deductions_payable_account_code") or "2330",
                        request.form.get("cash_account_code") or "1100",
                        request.form.get("bank_account_code") or "1200",
                        rules_row["id"],
                    ),
                )
                conn.commit()
            conn.close()
            flash("تم تحديث قواعد الرواتب بنجاح.", "success")
            return redirect(url_for("hr.payroll", month=request.form.get("adjustment_month") or date.today().strftime("%Y-%m")))

        employee_id = request.form.get("employee_id")
        adjustment_month = request.form.get("adjustment_month") or date.today().strftime("%Y-%m")
        adjustment_type = request.form.get("adjustment_type") or "allowance"
        title = request.form.get("title") or "تسوية مرتب"
        amount = float(request.form.get("amount") or 0)
        notes = request.form.get("notes")
        cur.execute(
            """
            INSERT INTO hr_salary_adjustments(employee_id, adjustment_month, adjustment_type, title, amount, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (employee_id, adjustment_month, adjustment_type, title, amount, notes),
        )
        conn.commit()
        conn.close()
        flash("تم حفظ التسوية بنجاح.", "success")
        return redirect(url_for("hr.payroll", month=adjustment_month))

    month = request.args.get("month") or date.today().strftime("%Y-%m")
    runs = cur.execute("SELECT * FROM hr_payroll_runs ORDER BY payroll_month DESC, id DESC").fetchall()
    employees = cur.execute(f"SELECT * FROM hr_employees e WHERE {_active_filter()} ORDER BY full_name").fetchall()
    adjustments = cur.execute(
        """
        SELECT a.*, e.full_name
        FROM hr_salary_adjustments a
        JOIN hr_employees e ON e.id = a.employee_id
        WHERE a.adjustment_month=?
        ORDER BY a.id DESC
        """,
        (month,),
    ).fetchall()
    rules = cur.execute("SELECT * FROM hr_payroll_rules ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return render_template(
        "hr/payroll.html",
        runs=runs,
        employees=employees,
        adjustments=adjustments,
        month=month,
        rules=rules,
        adjustment_labels=PAYROLL_ADJUSTMENT_LABELS,
    )


@hr_bp.route("/payroll/generate", methods=["POST"])
def payroll_generate():
    payroll_month = request.form.get("payroll_month") or date.today().strftime("%Y-%m")
    run_date = request.form.get("run_date") or date.today().isoformat()
    payment_method = request.form.get("payment_method") or "accrued"

    conn = get_db()
    cur = conn.cursor()
    existing = cur.execute("SELECT id FROM hr_payroll_runs WHERE payroll_month=?", (payroll_month,)).fetchone()
    if existing:
        conn.close()
        flash("يوجد مسير رواتب لهذا الشهر بالفعل.", "warning")
        return redirect(url_for("hr.payroll_detail", run_id=existing["id"]))

    rules = cur.execute("SELECT * FROM hr_payroll_rules ORDER BY id DESC LIMIT 1").fetchone()
    late_rate = _rule_float(rules, "late_deduction_per_min", 0.0)
    absent_rate = _rule_float(rules, "absent_day_deduction_rate", 1.0)
    overtime_rate = _rule_float(rules, "overtime_rate_per_hour", 0.0)
    overtime_multiplier = _rule_float(rules, "overtime_multiplier", 1.35)

    cur.execute(
        """
        INSERT INTO hr_payroll_runs(payroll_month, run_date, status, posting_status, payment_method, created_by, notes)
        VALUES (?, ?, 'draft', 'unposted', ?, ?, ?)
        """,
        (payroll_month, run_date, payment_method, session.get("username", "admin"), request.form.get("notes")),
    )
    run_id = int(cur.lastrowid)

    employees = cur.execute(f"SELECT * FROM hr_employees e WHERE {_active_filter()} ORDER BY full_name").fetchall()
    total_gross = 0.0
    total_deductions = 0.0
    total_net = 0.0

    for employee in employees:
        attendance = cur.execute(
            """
            SELECT
                COUNT(CASE WHEN status='present' THEN 1 END) AS present_days,
                COUNT(CASE WHEN status='absent' THEN 1 END) AS absent_days,
                COALESCE(SUM(late_minutes),0) AS late_minutes,
                COALESCE(SUM(early_leave_minutes),0) AS early_minutes,
                COALESCE(SUM(overtime_minutes),0) AS overtime_minutes
            FROM hr_attendance
            WHERE employee_id=? AND substr(work_date,1,7)=?
            """,
            (employee["id"], payroll_month),
        ).fetchone()

        adjustment_rows = cur.execute(
            """
            SELECT adjustment_type, COALESCE(SUM(amount),0) AS amount
            FROM hr_salary_adjustments
            WHERE employee_id=? AND adjustment_month=?
            GROUP BY adjustment_type
            """,
            (employee["id"], payroll_month),
        ).fetchall()
        adjustment_map = {row["adjustment_type"]: float(row["amount"] or 0) for row in adjustment_rows}

        base_salary = float(employee["base_salary"] or 0)
        hourly_rate = _hourly_rate(base_salary, employee, rules)
        scheduled_work_hours = round(_scheduled_daily_minutes(employee) / 60, 2)
        present_days = int(attendance["present_days"] or 0)
        absent_days = int(attendance["absent_days"] or 0)
        late_minutes = int(attendance["late_minutes"] or 0)
        early_minutes = int(attendance["early_minutes"] or 0)
        overtime_minutes = int(attendance["overtime_minutes"] or 0)

        allowance_amount = adjustment_map.get("allowance", 0.0)
        bonus_amount = adjustment_map.get("bonus", 0.0)
        incentive_amount = adjustment_map.get("incentive", 0.0)
        insurance_amount, insurance_base_salary = _employee_insurance_amount(base_salary, rules)
        if "insurance" in adjustment_map:
            insurance_amount = adjustment_map.get("insurance", 0.0)
        employer_insurance_amount = _employer_insurance_amount(insurance_base_salary, rules)
        tax_amount = adjustment_map.get("tax", 0.0)
        loan_amount = adjustment_map.get("loan", 0.0)
        penalty_amount = adjustment_map.get("penalty", 0.0)
        other_deduction = adjustment_map.get("deduction", 0.0)
        derived_overtime_rate = overtime_rate if overtime_rate > 0 else (hourly_rate * overtime_multiplier)
        overtime_amount = adjustment_map.get("overtime", 0.0) + ((overtime_minutes / 60) * derived_overtime_rate)
        minute_rate = late_rate if late_rate > 0 else (hourly_rate / 60)
        tardiness_deduction = (late_minutes + early_minutes) * minute_rate
        absence_deduction = absent_days * scheduled_work_hours * hourly_rate * absent_rate
        attendance_deductions = tardiness_deduction + absence_deduction
        taxable_salary = max(0.0, base_salary + allowance_amount + bonus_amount + incentive_amount + overtime_amount - attendance_deductions)
        if "tax" not in adjustment_map:
            tax_amount = _monthly_salary_tax(gross_salary=taxable_salary, attendance_deductions=0.0, employee_insurance_amount=insurance_amount, rules=rules)

        gross_salary = base_salary + allowance_amount + bonus_amount + incentive_amount + overtime_amount
        line_total_deductions = (
            insurance_amount
            + tax_amount
            + loan_amount
            + penalty_amount
            + tardiness_deduction
            + absence_deduction
            + other_deduction
        )
        net_salary = max(0.0, gross_salary - line_total_deductions)

        total_gross += gross_salary
        total_deductions += line_total_deductions
        total_net += net_salary

        cur.execute(
            """
            INSERT INTO hr_payroll_lines(
                run_id, employee_id, base_salary, hourly_rate, scheduled_work_hours,
                allowance_amount, bonus_amount, incentive_amount, overtime_amount,
                insurance_amount, employer_insurance_amount, insurance_base_salary,
                tax_amount, taxable_salary, loan_amount, penalty_amount, late_deduction, absence_deduction,
                other_deduction, gross_salary, total_deductions, net_salary,
                present_days, absent_days, late_minutes, early_minutes, overtime_minutes,
                posting_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unposted')
            """,
            (
                run_id,
                employee["id"],
                round(base_salary, 2),
                round(hourly_rate, 2),
                round(scheduled_work_hours, 2),
                round(allowance_amount, 2),
                round(bonus_amount, 2),
                round(incentive_amount, 2),
                round(overtime_amount, 2),
                round(insurance_amount, 2),
                round(employer_insurance_amount, 2),
                round(insurance_base_salary, 2),
                round(tax_amount, 2),
                round(taxable_salary, 2),
                round(loan_amount, 2),
                round(penalty_amount, 2),
                round(tardiness_deduction, 2),
                round(absence_deduction, 2),
                round(other_deduction, 2),
                round(gross_salary, 2),
                round(line_total_deductions, 2),
                round(net_salary, 2),
                present_days,
                absent_days,
                late_minutes,
                early_minutes,
                overtime_minutes,
            ),
        )

    cur.execute(
        "UPDATE hr_payroll_runs SET total_gross=?, total_deductions=?, total_net=? WHERE id=?",
        (round(total_gross, 2), round(total_deductions, 2), round(total_net, 2), run_id),
    )
    conn.commit()
    conn.close()
    flash("تم إنشاء مسير الرواتب بنجاح.", "success")
    return redirect(url_for("hr.payroll_detail", run_id=run_id))


@hr_bp.route("/payroll/<int:run_id>")
def payroll_detail(run_id: int):
    conn = get_db()
    cur = conn.cursor()
    run = cur.execute("SELECT * FROM hr_payroll_runs WHERE id=?", (run_id,)).fetchone()
    if not run:
        conn.close()
        flash("مسير الرواتب غير موجود.", "danger")
        return redirect(url_for("hr.payroll"))

    lines = cur.execute(
        """
        SELECT
            l.*,
            e.full_name,
            e.employee_code,
            e.job_title,
            d.name AS department_name
        FROM hr_payroll_lines l
        JOIN hr_employees e ON e.id = l.employee_id
        LEFT JOIN hr_departments d ON d.id = e.department_id
        WHERE l.run_id=?
        ORDER BY e.full_name
        """,
        (run_id,),
    ).fetchall()
    rules = cur.execute("SELECT * FROM hr_payroll_rules ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return render_template("hr/payroll_detail.html", run=run, lines=lines, rules=rules)


@hr_bp.route("/payroll/<int:run_id>/payslip/<int:employee_id>")
def payroll_payslip(run_id: int, employee_id: int):
    conn = get_db()
    cur = conn.cursor()
    row = cur.execute(
        """
        SELECT
            r.id AS run_id,
            r.payroll_month,
            r.run_date,
            r.status AS run_status,
            l.*,
            e.employee_code,
            e.full_name,
            e.job_title,
            e.base_salary AS employee_base_salary,
            d.name AS department_name
        FROM hr_payroll_runs r
        JOIN hr_payroll_lines l ON l.run_id = r.id
        JOIN hr_employees e ON e.id = l.employee_id
        LEFT JOIN hr_departments d ON d.id = e.department_id
        WHERE r.id=? AND e.id=?
        """,
        (run_id, employee_id),
    ).fetchone()
    if not row:
        conn.close()
        flash("شيت المرتب غير موجود.", "danger")
        return redirect(url_for("hr.payroll_detail", run_id=run_id))
    conn.close()
    return render_template("hr/payslip.html", payslip=row)


@hr_bp.route("/payroll/<int:run_id>/post", methods=["POST"])
def payroll_post(run_id: int):
    conn = get_db()
    cur = conn.cursor()
    run = cur.execute("SELECT * FROM hr_payroll_runs WHERE id=?", (run_id,)).fetchone()
    rules = cur.execute("SELECT * FROM hr_payroll_rules ORDER BY id DESC LIMIT 1").fetchone()
    if not run:
        conn.close()
        flash("مسير الرواتب غير موجود.", "danger")
        return redirect(url_for("hr.payroll"))
    if run["status"] != "draft" or run["posting_status"] == "posted":
        conn.close()
        flash("تم ترحيل هذا المسير من قبل أو أنه ليس في حالة مسودة.", "warning")
        return redirect(url_for("hr.payroll_detail", run_id=run_id))

    month = run["payroll_month"]
    duplicate_posted = cur.execute(
        """
        SELECT COUNT(*)
        FROM hr_payroll_lines current_lines
        JOIN hr_payroll_lines other_lines ON other_lines.employee_id = current_lines.employee_id
        JOIN hr_payroll_runs other_run ON other_run.id = other_lines.run_id
        WHERE current_lines.run_id = ?
          AND other_lines.run_id <> ?
          AND other_run.payroll_month = ?
          AND other_run.status IN ('posted', 'paid')
        """,
        (run_id, run_id, month),
    ).fetchone()[0]
    if int(duplicate_posted or 0) > 0:
        conn.close()
        flash("لا يمكن ترحيل المسير لأن هناك موظفين تم ترحيل مرتباتهم لهذا الشهر بالفعل.", "danger")
        return redirect(url_for("hr.payroll_detail", run_id=run_id))

    totals = cur.execute(
        """
        SELECT
            COALESCE(SUM(base_salary), 0) AS base_salary_total,
            COALESCE(SUM(allowance_amount + bonus_amount + incentive_amount + overtime_amount), 0) AS variable_total,
            COALESCE(SUM(insurance_amount), 0) AS insurance_total,
            COALESCE(SUM(employer_insurance_amount), 0) AS employer_insurance_total,
            COALESCE(SUM(tax_amount), 0) AS tax_total,
            COALESCE(SUM(loan_amount + penalty_amount + late_deduction + absence_deduction + other_deduction), 0) AS other_deductions_total
        FROM hr_payroll_lines
        WHERE run_id=?
        """,
        (run_id,),
    ).fetchone()

    try:
        _ensure_payroll_accounts(cur)
        salary_expense_code = rules["salary_expense_account_code"] or "5110"
        variable_code = rules["variable_compensation_account_code"] or "5115"
        employer_insurance_expense_code = rules["employer_insurance_expense_account_code"] or "5116"
        payable_code = rules["salary_payable_account_code"] or "2310"
        insurance_code = rules["insurance_payable_account_code"] or "2220"
        tax_code = rules["tax_payable_account_code"] or "2340"
        deductions_code = rules["deductions_payable_account_code"] or "2330"

        first_journal_id = None
        for debit_code, credit_code, amount, description in (
            (salary_expense_code, payable_code, totals["base_salary_total"], f"إثبات الرواتب الأساسية لشهر {month}"),
            (variable_code, payable_code, totals["variable_total"], f"إثبات البدلات والحوافز لشهر {month}"),
            (payable_code, insurance_code, totals["insurance_total"], f"إثبات التأمينات المستحقة لشهر {month}"),
            (payable_code, tax_code, totals["tax_total"], f"إثبات الضرائب المستحقة لشهر {month}"),
            (payable_code, deductions_code, totals["other_deductions_total"], f"إثبات الاستقطاعات الأخرى لشهر {month}"),
        ):
            journal_id = _create_journal_by_codes(
                cur,
                run["run_date"],
                description,
                debit_code,
                credit_code,
                amount,
                source_type="hr_payroll",
                source_id=run_id,
            )
            if first_journal_id is None and journal_id is not None:
                first_journal_id = journal_id

        employer_insurance_journal = _create_journal_by_codes(
            cur,
            run["run_date"],
            f"Employer social insurance contribution for payroll month {month}",
            employer_insurance_expense_code,
            insurance_code,
            totals["employer_insurance_total"],
            source_type="hr_payroll",
            source_id=run_id,
        )
        if first_journal_id is None and employer_insurance_journal is not None:
            first_journal_id = employer_insurance_journal

        cur.execute(
            """
            UPDATE hr_payroll_runs
            SET status='posted',
                posting_status='posted',
                journal_id=?,
                posted_at=?,
                posted_by=?
            WHERE id=?
            """,
            (first_journal_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), session.get("username", "admin"), run_id),
        )
        cur.execute(
            "UPDATE hr_payroll_lines SET posting_status='posted', journal_id=? WHERE run_id=?",
            (first_journal_id, run_id),
        )
        conn.commit()
        flash("تم اعتماد وترحيل مسير الرواتب محاسبياً.", "success")
    except Exception as exc:
        conn.rollback()
        flash(f"فشل ترحيل مسير الرواتب: {exc}", "danger")
    finally:
        conn.close()

    return redirect(url_for("hr.payroll_detail", run_id=run_id))


@hr_bp.route("/payroll/<int:run_id>/pay", methods=["POST"])
def payroll_pay(run_id: int):
    conn = get_db()
    cur = conn.cursor()
    run = cur.execute("SELECT * FROM hr_payroll_runs WHERE id=?", (run_id,)).fetchone()
    rules = cur.execute("SELECT * FROM hr_payroll_rules ORDER BY id DESC LIMIT 1").fetchone()
    if not run:
        conn.close()
        flash("مسير الرواتب غير موجود.", "danger")
        return redirect(url_for("hr.payroll"))
    if run["status"] != "posted":
        conn.close()
        flash("يجب اعتماد مسير الرواتب أولاً قبل الصرف.", "warning")
        return redirect(url_for("hr.payroll_detail", run_id=run_id))
    if run["payment_journal_id"]:
        conn.close()
        flash("تم تسجيل صرف الرواتب مسبقاً.", "warning")
        return redirect(url_for("hr.payroll_detail", run_id=run_id))

    payment_method = run["payment_method"] or "accrued"
    credit_code = rules["cash_account_code"] or "1100"
    if payment_method == "bank":
        credit_code = rules["bank_account_code"] or "1200"
    elif payment_method == "cash":
        credit_code = rules["cash_account_code"] or "1100"

    try:
        _ensure_payroll_accounts(cur)
        payment_journal_id = _create_journal_by_codes(
            cur,
            date.today().isoformat(),
            f"صرف رواتب شهر {run['payroll_month']}",
            rules["salary_payable_account_code"] or "2310",
            credit_code,
            run["total_net"],
            source_type="hr_payroll_payment",
            source_id=run_id,
        )
        cur.execute(
            "UPDATE hr_payroll_runs SET status='paid', payment_journal_id=? WHERE id=?",
            (payment_journal_id, run_id),
        )
        conn.commit()
        flash("تم تسجيل صرف الرواتب بنجاح.", "success")
    except Exception as exc:
        conn.rollback()
        flash(f"فشل تسجيل صرف الرواتب: {exc}", "danger")
    finally:
        conn.close()

    return redirect(url_for("hr.payroll_detail", run_id=run_id))
