from pathlib import Path
from datetime import datetime
import sys
import re

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PENDING_DIR = PROJECT_ROOT / "AI_TASKS" / "pending"
PENDING_DIR.mkdir(parents=True, exist_ok=True)


def slugify_arabic(text):
    text = text.strip().lower()
    mapping = {
        "الفواتير": "invoices",
        "فاتورة": "invoice",
        "المبيعات": "sales",
        "المشتريات": "purchases",
        "المخازن": "inventory",
        "المخزون": "inventory",
        "الداشبورد": "dashboard",
        "لوحة": "dashboard",
        "الذكاء": "ai",
        "الاصطناعي": "ai",
        "تعديل": "improve",
        "تحسين": "improve",
        "اضافة": "add",
        "إضافة": "add",
        "زر": "button",
        "شكل": "ui",
        "موبايل": "mobile",
        "شاشة": "screen",
    }

    words = []
    for ar, en in mapping.items():
        if ar in text:
            words.append(en)

    if not words:
        words = ["arabic", "task"]

    slug = "_".join(dict.fromkeys(words))
    slug = re.sub(r"[^a-z0-9_]+", "_", slug)
    return slug[:60]


def detect_priority(text):
    if any(w in text for w in ["عاجل", "مهم جدا", "ضروري", "خطير"]):
        return "High"
    if any(w in text for w in ["بسيط", "تجميلي", "شكل"]):
        return "Low"
    return "Medium"


def detect_risk_notes(text):
    notes = [
        "Preserve existing logic",
        "Do not modify accounting posting logic",
        "Do not modify database.db",
        "Do not drop tables or columns",
        "Run AI pipeline and sandbox validation before approval",
    ]

    if any(w in text for w in ["فواتير", "فاتورة", "مبيعات", "مشتريات", "قيود", "حسابات", "مخزون"]):
        notes.append("This task may affect ERP business modules; require careful review.")

    return notes


def create_task(arabic_request):
    slug = slugify_arabic(arabic_request)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_name = f"{slug}_{timestamp}.md"

    priority = detect_priority(arabic_request)
    notes = detect_risk_notes(arabic_request)

    content = f"""# Task: {slug}

## Status
Pending

## Priority
{priority}

## Original Arabic Request
{arabic_request}

## Goal
Convert the Arabic request into a safe LedgerX ERP development task and execute it through the AI automation workflow.

## Requirements
- Understand the Arabic request carefully.
- Preserve existing ERP behavior.
- Preserve accounting integrity.
- Preserve database integrity.
- Do not modify protected accounting logic without review.
- Generate prompt, risk report, patch plan, sandbox validation, gate report, and approval notification.
- Require human approval before applying production changes unless policy explicitly allows auto-apply.

## Safety Notes
{chr(10).join("- " + n for n in notes)}

## Created At
{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

    out = PENDING_DIR / task_name
    out.write_text(content, encoding="utf-8")

    print("Arabic request converted to task:")
    print(out)
    return out


def main():
    if len(sys.argv) < 2:
        print('Usage:')
        print('python AI_SYSTEM/intake_engine/arabic_task_intake.py "اكتب المطلوب هنا بالعربي"')
        return 1

    arabic_request = " ".join(sys.argv[1:]).strip()
    create_task(arabic_request)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
