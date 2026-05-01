# -*- coding: utf-8 -*-
"""
LedgerX Payroll Navigation Integration
Run once from the project root:
    python tools/install_payroll_nav.py
"""

from pathlib import Path
import shutil
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
LAYOUT = TEMPLATES / "layout.html"
HR_DIR = TEMPLATES / "hr"

PAYROLL_LINK_LAYOUT = """
<a href="{{ url_for('hr.payroll') }}" class="nav-link">
    <i class="bi bi-cash-stack"></i>
    <span>Payroll الرواتب</span>
</a>
""".strip()

PAYROLL_LINK_MINI = """<a href="{{ url_for('hr.payroll') }}">Payroll الرواتب</a>"""


def backup(path: Path):
    if path.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = path.with_suffix(path.suffix + f".bak_{stamp}")
        shutil.copy2(path, dst)
        print(f"Backup created: {dst}")


def patch_layout():
    if not LAYOUT.exists():
        print("SKIP: templates/layout.html not found")
        return

    text = LAYOUT.read_text(encoding="utf-8")
    if "url_for('hr.payroll')" in text or 'url_for("hr.payroll")' in text or "/hr/payroll" in text:
        print("OK: Payroll link already exists in layout.html")
        return

    backup(LAYOUT)

    candidates = [
        'url_for("hr.dashboard")',
        "url_for('hr.dashboard')",
        'href="/hr"',
        "href='/hr'",
        'href="{{ url_for("hr.employees") }}"',
        "href=\"{{ url_for('hr.employees') }}\"",
        'href="/employees"',
    ]

    inserted = False
    for marker in candidates:
        idx = text.find(marker)
        if idx != -1:
            end = text.find("</a>", idx)
            if end != -1:
                end += len("</a>")
                text = text[:end] + "\n" + PAYROLL_LINK_LAYOUT + "\n" + text[end:]
                inserted = True
                break

    if not inserted:
        for marker in ["</aside>", "{% block content %}", "<main"]:
            idx = text.find(marker)
            if idx != -1:
                text = text[:idx] + "\n" + PAYROLL_LINK_LAYOUT + "\n" + text[idx:]
                inserted = True
                break

    if not inserted:
        text += "\n<!-- Add Payroll manually: " + PAYROLL_LINK_LAYOUT.replace("--", "") + " -->\n"

    LAYOUT.write_text(text, encoding="utf-8")
    print("DONE: layout.html updated with Payroll link")


def patch_hr_templates():
    if not HR_DIR.exists():
        print("SKIP: templates/hr not found")
        return

    targets = ["dashboard.html", "employees.html", "attendance.html", "leaves.html", "reports.html", "payroll.html"]
    for name in targets:
        path = HR_DIR / name
        if not path.exists():
            continue

        text = path.read_text(encoding="utf-8")
        if "url_for('hr.payroll')" in text or 'url_for("hr.payroll")' in text:
            print(f"OK: Payroll link already exists in hr/{name}")
            continue

        backup(path)

        markers = [
            '<a href="{{ url_for(\'hr.reports\') }}">📊 التقارير</a>',
            '<a href="{{ url_for("hr.reports") }}">📊 التقارير</a>',
            '<a href="{{ url_for(\'hr.reports\') }}">التقارير</a>',
            '<a href="{{ url_for("hr.reports") }}">التقارير</a>',
        ]

        done = False
        for marker in markers:
            if marker in text:
                text = text.replace(marker, marker + "\n  " + PAYROLL_LINK_MINI, 1)
                done = True
                break

        if not done:
            hero_pos = text.find("hr-hero")
            hero_end = text.find("</div>", hero_pos) if hero_pos != -1 else -1
            if hero_end != -1:
                hero_end += len("</div>")
                mini = """
<div class="hr-mini-nav">
  <a href="{{ url_for('hr.dashboard') }}">لوحة HR</a>
  <a href="{{ url_for('hr.employees') }}">الموظفون</a>
  <a href="{{ url_for('hr.attendance') }}">الحضور</a>
  <a href="{{ url_for('hr.leaves') }}">الإجازات</a>
  <a href="{{ url_for('hr.reports') }}">التقارير</a>
  <a href="{{ url_for('hr.payroll') }}">Payroll الرواتب</a>
</div>
"""
                text = text[:hero_end] + "\n" + mini + "\n" + text[hero_end:]
                done = True

        path.write_text(text, encoding="utf-8")
        print(f"DONE: hr/{name} updated")


if __name__ == "__main__":
    patch_layout()
    patch_hr_templates()
    print("\nFinished. Restart Flask and test:")
    print("  /hr/")
    print("  /hr/payroll")
