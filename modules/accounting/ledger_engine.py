"""
Ledger Engine
-------------
نواة مركزية آمنة لإنشاء القيود المحاسبية.

ملاحظة مهمة:
النسخة الحالية من قاعدة البيانات تستخدم جدول journal بشكل مبسط:
- debit_account_id
- credit_account_id
- amount

لذلك هذه النواة تدعم هذا الشكل الحالي، مع تجهيز دوال مستقبلية
للتحول لاحقًا إلى قيود متعددة الأطراف بدون كسر النظام.
"""


def get_account_id_by_code(cur, account_code):
    """إرجاع ID الحساب من كود شجرة الحسابات."""
    cur.execute("SELECT id FROM accounts WHERE code=?", (str(account_code),))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"الحساب غير موجود في شجرة الحسابات: {account_code}")
    return row[0]


def post_simple_entry(
    cur,
    date,
    description,
    debit_code,
    credit_code,
    amount,
    source_type="auto",
    source_id=None,
    cost_center_id=None,
):
    """
    إنشاء قيد بسيط من طرفين متوافق مع جدول journal الحالي.

    مثال:
        post_simple_entry(cur, date, "فاتورة بيع", "1100", "4100", 1000)

    يرجع:
        journal_id
    """
    amount = float(amount or 0)
    if amount <= 0:
        raise ValueError("مبلغ القيد يجب أن يكون أكبر من صفر")
    if str(debit_code) == str(credit_code):
        raise ValueError("لا يمكن أن يكون الحساب المدين هو نفسه الحساب الدائن")

    debit_account_id = get_account_id_by_code(cur, debit_code)
    credit_account_id = get_account_id_by_code(cur, credit_code)

    cur.execute(
        """
        INSERT INTO journal(
            date, description, debit_account_id, credit_account_id, amount,
            status, source_type, source_id, cost_center_id
        )
        VALUES (?, ?, ?, ?, ?, 'posted', ?, ?, ?)
        """,
        (
            date,
            description,
            debit_account_id,
            credit_account_id,
            amount,
            source_type or "auto",
            source_id,
            cost_center_id,
        ),
    )
    return cur.lastrowid


def post_entry(cur, date, description, lines, source_type="auto", source_id=None, cost_center_id=None):
    """
    واجهة مستقبلية للقيود متعددة الأطراف.

    حاليًا تدعم فقط قيد من طرفين حتى تظل متوافقة مع جدول journal الحالي.
    lines = [
        {"account_code": "1100", "debit": 1000, "credit": 0},
        {"account_code": "4100", "debit": 0, "credit": 1000},
    ]
    """
    debit_lines = [line for line in lines if float(line.get("debit", 0) or 0) > 0]
    credit_lines = [line for line in lines if float(line.get("credit", 0) or 0) > 0]

    total_debit = sum(float(line.get("debit", 0) or 0) for line in lines)
    total_credit = sum(float(line.get("credit", 0) or 0) for line in lines)

    if round(total_debit, 2) != round(total_credit, 2):
        raise ValueError("القيد غير متوازن")
    if len(debit_lines) != 1 or len(credit_lines) != 1:
        raise ValueError("النظام الحالي يدعم قيدًا بسيطًا من مدين واحد ودائن واحد فقط")

    debit_line = debit_lines[0]
    credit_line = credit_lines[0]
    debit_code = debit_line.get("account_code") or debit_line.get("code")
    credit_code = credit_line.get("account_code") or credit_line.get("code")

    if not debit_code or not credit_code:
        raise ValueError("يجب إرسال account_code لكل طرف في القيد")

    return post_simple_entry(
        cur,
        date,
        description,
        debit_code,
        credit_code,
        total_debit,
        source_type=source_type,
        source_id=source_id,
        cost_center_id=cost_center_id,
    )
