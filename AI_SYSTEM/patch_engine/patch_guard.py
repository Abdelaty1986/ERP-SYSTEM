from pathlib import Path

PROTECTED_PATH_PATTERNS = [
    "database.db",
    "ledger.html",
    "journal",
    "trial_balance",
    "posting",
    "inventory",
    "migrations.py",
    "payments",
    "receipts",
]

BLOCKED_EXTENSIONS = {
    ".db",
    ".sqlite",
    ".sqlite3",
}

def is_blocked_file(path):
    p = Path(path)
    lowered = str(p).lower()
    name = p.name.lower()

    if p.suffix.lower() in BLOCKED_EXTENSIONS:
        return True, "Database files are protected."

    normalized = lowered.replace("\\", "/")

    for pattern in PROTECTED_PATH_PATTERNS:
        pattern = pattern.lower()
        if pattern in {"ledger.html", "migrations.py", "database.db"}:
            if name == pattern:
                return True, f"Protected file matched: {pattern}"
        elif pattern in normalized:
            return True, f"Protected area matched: {pattern}"

    return False, ""

def guard_patch_plan(files):
    blocked = []
    allowed = []

    for file in files:
        is_blocked, reason = is_blocked_file(file)
        item = {"file": file, "reason": reason}

        if is_blocked:
            blocked.append(item)
        else:
            allowed.append(item)

    return {
        "safe": len(blocked) == 0,
        "allowed": allowed,
        "blocked": blocked,
    }
