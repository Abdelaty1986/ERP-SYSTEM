import re


DEFAULT_DEPARTMENTS = [
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
]

PAYROLL_ACCOUNT_DEFAULTS = [
    ("5110", "مرتبات الإدارة", "مصروفات"),
    ("5115", "بدلات وحوافز وأجر إضافي", "مصروفات"),
    ("5170", "حصة الشركة في التأمينات الاجتماعية", "مصروفات"),
    ("2220", "تأمينات اجتماعية مستحقة", "خصوم"),
    ("2310", "أجور مستحقة", "خصوم"),
    ("2330", "استقطاعات عاملين مستحقة", "خصوم"),
    ("2340", "ضريبة كسب عمل مستحقة", "خصوم"),
    ("1100", "الخزنة", "أصول"),
    ("1200", "البنك", "أصول"),
]

EMPLOYEE_CODE_PATTERN = re.compile(r"^EMP-(\d+)$", re.IGNORECASE)


def _table_has_column(cur, table_name, column_name):
    cur.execute(f"PRAGMA table_info({table_name})")
    return any(row[1] == column_name for row in cur.fetchall())


def _add_column_if_missing(cur, table_name, column_name, definition):
    if not _table_has_column(cur, table_name, column_name):
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def _extract_code_number(code):
    if not code:
        return None
    match = EMPLOYEE_CODE_PATTERN.match(str(code).strip())
    if not match:
        return None
    return int(match.group(1))


def generate_next_employee_code(cur):
    cur.execute("SELECT employee_code, code FROM employees")
    next_number = 1
    for row in cur.fetchall():
        for value in row:
            number = _extract_code_number(value)
            if number and number >= next_number:
                next_number = number + 1
    return f"EMP-{next_number:03d}"


def ensure_hr_support_schema(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS departments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    _add_column_if_missing(cur, "employees", "employee_code", "TEXT")
    _add_column_if_missing(cur, "employees", "department_id", "INTEGER")
    _add_column_if_missing(cur, "employees", "is_active", "INTEGER NOT NULL DEFAULT 1")

    _add_column_if_missing(cur, "payroll_runs", "posting_status", "TEXT NOT NULL DEFAULT 'unposted'")
    _add_column_if_missing(cur, "payroll_runs", "payment_method", "TEXT NOT NULL DEFAULT 'accrued'")
    _add_column_if_missing(cur, "payroll_runs", "posted_at", "TEXT")
    _add_column_if_missing(cur, "payroll_runs", "posted_by", "TEXT")
    _add_column_if_missing(cur, "payroll_runs", "payment_journal_id", "INTEGER")
    _add_column_if_missing(cur, "payroll_runs", "allowances_journal_id", "INTEGER")
    _add_column_if_missing(cur, "payroll_runs", "deductions_journal_id", "INTEGER")

    _add_column_if_missing(cur, "payroll_lines", "benefits", "REAL NOT NULL DEFAULT 0")
    _add_column_if_missing(cur, "payroll_lines", "incentives", "REAL NOT NULL DEFAULT 0")
    _add_column_if_missing(cur, "payroll_lines", "overtime", "REAL NOT NULL DEFAULT 0")
    _add_column_if_missing(cur, "payroll_lines", "advances", "REAL NOT NULL DEFAULT 0")
    _add_column_if_missing(cur, "payroll_lines", "penalties", "REAL NOT NULL DEFAULT 0")
    _add_column_if_missing(cur, "payroll_lines", "absence_deduction", "REAL NOT NULL DEFAULT 0")
    _add_column_if_missing(cur, "payroll_lines", "tardiness_deduction", "REAL NOT NULL DEFAULT 0")
    _add_column_if_missing(cur, "payroll_lines", "total_deductions", "REAL NOT NULL DEFAULT 0")
    _add_column_if_missing(cur, "payroll_lines", "posting_status", "TEXT NOT NULL DEFAULT 'unposted'")

    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_departments_name ON departments(name)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_employees_employee_code ON employees(employee_code)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_employees_department_id ON employees(department_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_employees_is_active ON employees(is_active, status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_payroll_runs_period ON payroll_runs(period)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_payroll_lines_run_employee ON payroll_lines(run_id, employee_id)")

    for department_name in DEFAULT_DEPARTMENTS:
        cur.execute("INSERT OR IGNORE INTO departments(name) VALUES (?)", (department_name,))

    cur.execute("SELECT id, code, employee_code FROM employees ORDER BY id")
    used_codes = set()
    pending_updates = []
    for employee_id, legacy_code, employee_code in cur.fetchall():
        candidate = (employee_code or "").strip()
        if candidate and candidate not in used_codes:
            used_codes.add(candidate)
            if not legacy_code:
                pending_updates.append((candidate, candidate, employee_id))
            continue
        candidate = generate_next_employee_code_from_set(used_codes)
        used_codes.add(candidate)
        pending_updates.append((candidate, legacy_code or candidate, employee_id))

    for employee_code, legacy_code, employee_id in pending_updates:
        cur.execute(
            "UPDATE employees SET employee_code=?, code=COALESCE(NULLIF(code,''), ?) WHERE id=?",
            (employee_code, legacy_code, employee_id),
        )

    cur.execute(
        """
        UPDATE employees
        SET department_id=(
            SELECT d.id
            FROM departments d
            WHERE d.name=employees.department
            LIMIT 1
        )
        WHERE department_id IS NULL
          AND COALESCE(department, '') <> ''
        """
    )
    cur.execute("UPDATE employees SET is_active=1 WHERE is_active IS NULL")
    cur.execute("UPDATE payroll_runs SET posting_status='posted' WHERE status='posted' AND COALESCE(journal_id, tax_journal_id, insurance_journal_id, company_insurance_journal_id) IS NOT NULL")
    cur.execute("UPDATE payroll_runs SET posting_status='unposted' WHERE posting_status IS NULL OR posting_status=''")
    cur.execute("UPDATE payroll_lines SET total_deductions=COALESCE(insurance_employee,0)+COALESCE(tax,0)+COALESCE(other_deductions,0)+COALESCE(advances,0)+COALESCE(penalties,0)+COALESCE(absence_deduction,0)+COALESCE(tardiness_deduction,0) WHERE COALESCE(total_deductions,0)=0")
    cur.execute("UPDATE payroll_lines SET posting_status='posted' WHERE posting_status IS NULL AND run_id IN (SELECT id FROM payroll_runs WHERE posting_status='posted')")
    cur.execute("UPDATE payroll_lines SET posting_status='unposted' WHERE posting_status IS NULL")


def generate_next_employee_code_from_set(used_codes):
    next_number = 1
    while True:
        candidate = f"EMP-{next_number:03d}"
        if candidate not in used_codes:
            return candidate
        next_number += 1


def get_department(cur, department_id):
    if not department_id:
        return None
    cur.execute("SELECT id, name FROM departments WHERE id=?", (department_id,))
    return cur.fetchone()


def ensure_payroll_accounts(cur):
    for code, name, account_type in PAYROLL_ACCOUNT_DEFAULTS:
        cur.execute("SELECT id FROM accounts WHERE code=?", (code,))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE accounts SET name=?, type=? WHERE code=?", (name, account_type, code))
        else:
            cur.execute(
                "INSERT INTO accounts(code, name, type) VALUES (?, ?, ?)",
                (code, name, account_type),
            )


def payment_method_label(payment_method):
    return {
        "accrued": "استحقاق",
        "cash": "صندوق",
        "bank": "بنك",
    }.get(payment_method or "accrued", "استحقاق")


def payment_method_credit_code(payment_method):
    return {
        "cash": "1100",
        "bank": "1200",
    }.get(payment_method, "2310")
