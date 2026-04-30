"""
Ledger Engine (Foundation)
-------------------------
مسؤول عن إنشاء القيود المحاسبية بشكل مركزي وموحد.

الهدف:
- منع تكرار منطق القيود في كل شاشة
- ضمان توازن القيد
- ربط كل عملية بمصدرها (فاتورة - مردود - سند)
"""


def post_entry(cur, date, description, lines, source_type=None, source_id=None):
    """
    إنشاء قيد يومية متوازن.

    lines = [
        {"account_id": 1, "debit": 1000, "credit": 0},
        {"account_id": 2, "debit": 0, "credit": 1000}
    ]
    """

    total_debit = sum(l.get("debit", 0) for l in lines)
    total_credit = sum(l.get("credit", 0) for l in lines)

    if round(total_debit, 2) != round(total_credit, 2):
        raise ValueError("القيد غير متوازن")

    # إنشاء قيد رئيسي
    cur.execute(
        """
        INSERT INTO journal(date, description, status)
        VALUES (?, ?, 'posted')
        """,
        (date, description),
    )
    journal_id = cur.lastrowid

    # إنشاء تفاصيل القيد
    for line in lines:
        cur.execute(
            """
            INSERT INTO ledger(account_id, date, description, debit, credit, journal_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                line["account_id"],
                date,
                description,
                line.get("debit", 0),
                line.get("credit", 0),
                journal_id,
            ),
        )

    # ربط القيد بالمصدر (مستقبلي)
    if source_type and source_id:
        try:
            cur.execute(
                """
                INSERT INTO journal_sources(journal_id, source_type, source_id)
                VALUES (?, ?, ?)
                """,
                (journal_id, source_type, source_id),
            )
        except Exception:
            pass

    return journal_id
