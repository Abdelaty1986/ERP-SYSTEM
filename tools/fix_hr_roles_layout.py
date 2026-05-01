# -*- coding: utf-8 -*-
"""
Optional script to normalize HR naming in layout.html.
Run:
python tools/fix_hr_roles_layout.py
"""
from pathlib import Path
from datetime import datetime
import shutil

root = Path(__file__).resolve().parents[1]
layout = root / "templates" / "layout.html"

if layout.exists():
    backup = layout.with_suffix(".html.bak_hr_roles_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(layout, backup)
    text = layout.read_text(encoding="utf-8")
    replacements = {
        "شؤون العاملين": "إدارة الموارد البشرية",
        "شئون العاملين": "إدارة الموارد البشرية",
        "Payroll الرواتب": "تشغيل الرواتب",
        "Payroll": "تشغيل الرواتب",
        ">الموظفون<": ">إدارة الموظفين<",
        "<span>الموظفون</span>": "<span>إدارة الموظفين</span>",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    layout.write_text(text, encoding="utf-8")
    print("layout.html updated. Backup:", backup)
else:
    print("layout.html not found")
