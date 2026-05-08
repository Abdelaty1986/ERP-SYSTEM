from pathlib import Path
from datetime import datetime
import json
import subprocess

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = PROJECT_ROOT / "AI_TASKS" / "diff_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

HIGH_RISK_PATTERNS = [
    "database.db",
    "migrations.py",
    "ledger",
    "journal",
    "posting",
    "inventory",
    "payments",
    "receipts",
    "permissions",
    "users",
]

MEDIUM_RISK_PATTERNS = [
    "app.py",
    "modules/",
    "templates/layout.html",
]

LOW_RISK_PATTERNS = [
    "static/css",
    "templates/dev_ai_dashboard.html",
    "AI_SYSTEM/",
]

def run_git(args):
    result = subprocess.run(
        ["git"] + args,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()

def get_changed_files(mode="worktree"):
    if mode == "branch":
        output = run_git(["diff", "--name-only", "main...dev-ai"])
    else:
        output = run_git(["diff", "--name-only", "HEAD"])
    return [line.strip() for line in output.splitlines() if line.strip()]

def classify_file(path):
    lowered = path.lower().replace("\\", "/")
    name = Path(lowered).name

    if "__pycache__" in lowered or name.endswith(".pyc"):
        return "IGNORE"

    if lowered.startswith("ai_system/") or lowered.startswith("ai_tasks/"):
        return "LOW"

    if name.endswith(".md") or name.endswith(".json"):
        return "LOW"

    if lowered.startswith("static/css/"):
        return "LOW"

    if name in {"sales.html", "purchases.html"}:
        return "MEDIUM"

    if name == "app.py":
        return "MEDIUM"

    if name in {"ledger.html", "journal.html", "migrations.py", "database.db"}:
        return "HIGH"

    for pattern in HIGH_RISK_PATTERNS:
        if pattern in lowered:
            return "HIGH"

    for pattern in MEDIUM_RISK_PATTERNS:
        if pattern in lowered:
            return "MEDIUM"

    for pattern in LOW_RISK_PATTERNS:
        if pattern in lowered:
            return "LOW"

    return "UNKNOWN"

def build_report(mode="worktree"):
    files = get_changed_files(mode)
    analyzed = []

    risk_rank = {"IGNORE": 0, "LOW": 1, "UNKNOWN": 2, "MEDIUM": 3, "HIGH": 4}
    max_risk = "LOW"

    for file in files:
        risk = classify_file(file)
        analyzed.append({
            "file": file,
            "risk": risk,
        })

        if risk_rank[risk] > risk_rank[max_risk]:
            max_risk = risk

    report = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "GIT_BRANCH_DIFF" if mode == "branch" else "GIT_WORKTREE_DIFF",
        "changed_files_count": len(files),
        "overall_risk": max_risk if files else "NONE",
        "requires_manual_review": max_risk in ["MEDIUM", "HIGH", "UNKNOWN"],
        "changed_files": analyzed,
        "recommendation": (
            "Safe UI/system change review is enough."
            if max_risk == "LOW"
            else "Manual review required before commit or merge."
        ),
    }

    return report

def main():
    import sys
    mode = "branch" if len(sys.argv) > 1 and sys.argv[1] == "--branch" else "worktree"
    report = build_report(mode)
    out = REPORTS_DIR / f"diff_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Smart diff report generated:")
    print(out)
    print("Overall risk:", report["overall_risk"])
    print("Changed files:", report["changed_files_count"])

if __name__ == "__main__":
    main()
