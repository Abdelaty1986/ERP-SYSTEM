from pathlib import Path

BASE = Path(__file__).resolve().parent
# لو شغلت الملف من داخل فولدر المشروع سيستخدم فولدره، ولو حطيته في فولدر آخر عدل المسار هنا
PROJECT = BASE

files = {
    "app.py": [
        ("✅ Database initialized and migrated successfully.", "Database initialized and migrated successfully."),
        ("❌ Database init/migration failed:", "Database init/migration failed:"),
    ],
    "safe_ultimate_test.py": [
        ("FAILED ❌", "FAILED"),
        ("PASSED ✅", "PASSED"),
        ("❌ database.db not found at:", "database.db not found at:"),
    ],
    "db.py": [
        ('DB_PATH = os.path.join(BASE_DIR, "database.db")', 'DB_PATH = os.environ.get("ERP_DB_PATH", os.path.join(BASE_DIR, "database.db"))'),
    ],
}

for filename, replacements in files.items():
    path = PROJECT / filename
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    text = path.read_text(encoding="utf-8-sig")
    original = text
    for old, new in replacements:
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print(f"Updated: {filename}" if text != original else f"No change needed: {filename}")

print("Done. Run: python safe_ultimate_test.py --mode FULL_SAFE")
