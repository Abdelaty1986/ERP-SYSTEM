"""
Ledger Engine
-------------
محرك مركزي آمن لتسجيل القيود البسيطة في جدول journal.
في المرحلة الحالية يعتمد على نفس هيكل الجداول الحالي:
journal(date, description, debit_account_id, credit_account_id, amount, status, source_type, source_id, cost_center_id)
والـ ledger يتم بناؤه لاحقًا من journal عن طريق rebuild_ledger() الموجود في app.py.
"""

def get_account_id(cur, account_code):
    cur.execute("SELECT id FROM accounts WHERE code=?", (account_code,))
    row = cur.fetchone()
    return row[0] if row else None


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
    status="posted",
):
    """
    تسجيل قيد بسيط: طرف مدين وطرف دائن.

    يرجع journal_id.
    لا يعمل commit هنا؛ الـ commit مسؤولية الشاشة/العملية التي تستدعيه.
    """
    try:
        amount = float(amount or 0)
    except (TypeError, ValueError):
        amount = 0

    if amount <= 0:
        return None

    debit_id = get_account_id(cur, debit_code)
    credit_id = get_account_id(cur, credit_code)

    if not debit_id:
        raise ValueError(f"الحساب المدين غير موجود أو كوده غير صحيح: {debit_code}")
    if not credit_id:
        raise ValueError(f"الحساب الدائن غير موجود أو كوده غير صحيح: {credit_code}")
    if debit_id == credit_id:
        raise ValueError("لا يمكن أن يكون الحساب المدين هو نفسه الحساب الدائن.")

    cur.execute(
        """
        INSERT INTO journal(
            date, description, debit_account_id, credit_account_id,
            amount, status, source_type, source_id, cost_center_id
        )
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            date,
            description,
            debit_id,
            credit_id,
            amount,
            status,
            source_type or "auto",
            source_id,
            cost_center_id,
        ),
    )
    return cur.lastrowid


def post_entries(cur, entries, source_type="auto", source_id=None):
    """
    تسجيل أكثر من قيد بسيط في عملية واحدة.
    entries = [
        {"date": "...", "description": "...", "debit_code": "...", "credit_code": "...", "amount": ...},
    ]
    """
    journal_ids = []
    for entry in entries:
        journal_id = post_simple_entry(
            cur=cur,
            date=entry.get("date"),
            description=entry.get("description"),
            debit_code=entry.get("debit_code"),
            credit_code=entry.get("credit_code"),
            amount=entry.get("amount"),
            source_type=entry.get("source_type", source_type),
            source_id=entry.get("source_id", source_id),
            cost_center_id=entry.get("cost_center_id"),
            status=entry.get("status", "posted"),
        )
        if journal_id:
            journal_ids.append(journal_id)
    return journal_ids
