# -*- coding: utf-8 -*-
"""
LedgerX Layout HR Naming Fix
يشغل مرة واحدة من جذر المشروع:
    python tools/fix_layout_hr_names.py

الهدف:
- تغيير "شؤون العاملين" إلى "إدارة الموارد البشرية"
- تغيير "الموظفون" داخل HR إلى "إدارة الموظفين"
- تغيير Payroll / Payroll الرواتب إلى "تشغيل الرواتب"
- إضافة/تأكيد رابط تشغيل الرواتب في القائمة
- عمل Backup تلقائي قبل التعديل
"""

from pathlib import Path
from datetime import datetime
import shutil
import re

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "templates" / "layout.html"

PAYROLL_LINK = """
<a href="{{ url_for('hr.payroll') }}" class="nav-link">
    <i class="bi bi-cash-stack"></i>
    <span>تشغيل الرواتب</span>
</a>
""".strip()


def backup(path: Path):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = path.with_suffix(path.suffix + f".bak_{stamp}")
    shutil.copy2(path, dst)
    print(f"Backup created: {dst}")


def replace_text(text: str) -> str:
    replacements = {
        "شؤون العاملين": "إدارة الموارد البشرية",
        "شئون العاملين": "إدارة الموارد البشرية",
        "الموارد البشرية": "إدارة الموارد البشرية",
        "Payroll الرواتب": "تشغيل الرواتب",
        "Payroll": "تشغيل الرواتب",
        ">الموظفون<": ">إدارة الموظفين<",
        "> الموظفون <": "> إدارة الموظفين <",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # لو فيه span فيه الموظفون داخل HR links
    text = re.sub(r"<span>\s*الموظفون\s*</span>", "<span>إدارة الموظفين</span>", text)
    text = re.sub(r"<span>\s*Payroll\s*الرواتب\s*</span>", "<span>تشغيل الرواتب</span>", text)
    text = re.sub(r"<span>\s*Payroll\s*</span>", "<span>تشغيل الرواتب</span>", text)

    return text


def ensure_payroll_link(text: str) -> str:
    if "url_for('hr.payroll')" in text or 'url_for("hr.payroll")' in text or "/hr/payroll" in text:
        return text

    markers = [
        "إدارة الموظفين",
        "url_for('hr.employees')",
        'url_for("hr.employees")',
        "/hr/employees",
        "/employees",
    ]

    for marker in markers:
        idx = text.find(marker)
        if idx != -1:
            end = text.find("</a>", idx)
            if end != -1:
                end += len("</a>")
                return text[:end] + "\n" + PAYROLL_LINK + "\n" + text[end:]

    # fallback before aside end
    for marker in ["</aside>", "{% block content %}", "<main"]:
        idx = text.find(marker)
        if idx != -1:
            return text[:idx] + "\n" + PAYROLL_LINK + "\n" + text[idx:]

    return text + "\n<!-- Payroll link to add manually:\n" + PAYROLL_LINK + "\n-->\n"


def main():
    if not LAYOUT.exists():
        print("ERROR: templates/layout.html not found")
        return

    backup(LAYOUT)
    text = LAYOUT.read_text(encoding="utf-8")
    text = replace_text(text)
    text = ensure_payroll_link(text)
    LAYOUT.write_text(text, encoding="utf-8")
    print("DONE: layout.html HR names updated successfully.")
    print("Restart Flask then open /dashboard and /hr/payroll")


if __name__ == "__main__":
    main()
