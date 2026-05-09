from pathlib import Path
from datetime import datetime
import json
import subprocess

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_PLANS_DIR = PROJECT_ROOT / "AI_TASKS" / "test_plans"
TEST_PLANS_DIR.mkdir(parents=True, exist_ok=True)

def run_git(args):
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except FileNotFoundError:
        return ""

def get_changed_files(mode="worktree"):
    if mode == "branch":
        output = run_git(["diff", "--name-only", "main...dev-ai"])
    else:
        output = run_git(["diff", "--name-only", "HEAD"])
    ignored_parts = [
        "__pycache__",
        ".pyc",
        "AI_TASKS/validation_reports/",
        "AI_TASKS/diff_reports/",
        "AI_TASKS/patch_plans/",
        "AI_TASKS/patch_files/",
        "AI_TASKS/generated_prompts/",
        "AI_TASKS/risk_reports/",
    ]

    files = []
    for line in output.splitlines():
        item = line.strip()
        if not item:
            continue
        normalized = item.replace("\\", "/")
        if any(part in normalized for part in ignored_parts):
            continue
        files.append(item)

    return files

def select_tests(files):
    tests = set()
    reasons = []

    if not files:
        tests.add("quick_health_check")
        reasons.append("No changed files detected; run a quick health check only.")

    for file in files:
        lowered = file.lower().replace("\\", "/")

        if lowered.startswith("static/css/") or lowered.startswith("templates/"):
            tests.add("ui_smoke_test")
            reasons.append(f"UI file changed: {file}")

        if lowered == "app.py" or lowered.startswith("modules/"):
            tests.add("route_smoke_test")
            tests.add("workflow_validation")
            reasons.append(f"Core Flask/module file changed: {file}")

        if (
            "sales" in lowered
            or "invoice" in lowered
        ) and not lowered.startswith("static/css/"):
            tests.add("invoice_workflow_test")
            reasons.append(f"Sales/invoice area changed: {file}")

        if "purchase" in lowered or "purchases" in lowered:
            tests.add("purchase_workflow_test")
            reasons.append(f"Purchase area changed: {file}")

        if (
            "ledger" in lowered
            or "journal" in lowered
            or "posting" in lowered
        ) and not lowered.startswith("static/css/"):
            tests.add("ledger_integrity_test")
            reasons.append(f"Accounting ledger/posting area changed: {file}")

        if "migration" in lowered:
            tests.add("migration_safety_test")
            reasons.append(f"Migration-related file changed: {file}")

        if "permissions" in lowered or "users" in lowered:
            tests.add("permission_security_test")
            reasons.append(f"Permission/user area changed: {file}")

        if lowered.startswith("ai_system/"):
            tests.add("ai_pipeline_validation")
            reasons.append(f"AI system file changed: {file}")

    return sorted(tests), reasons

def build_test_plan(mode="worktree"):
    files = get_changed_files(mode)
    tests, reasons = select_tests(files)

    plan = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "GIT_BRANCH_DIFF" if mode == "branch" else "GIT_WORKTREE_DIFF",
        "changed_files_count": len(files),
        "changed_files": files,
        "selected_tests": tests,
        "reasons": reasons,
        "manual_review_required": any(t in tests for t in [
            "ledger_integrity_test",
            "permission_security_test",
            "migration_safety_test",
        ]),
    }
    return plan

def main():
    import sys
    mode = "branch" if len(sys.argv) > 1 and sys.argv[1] == "--branch" else "worktree"

    plan = build_test_plan(mode)
    out = TEST_PLANS_DIR / f"test_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Intelligent test plan generated:")
    print(out)
    print("Selected tests:", ", ".join(plan["selected_tests"]) or "none")
    print("Manual review required:", plan["manual_review_required"])

if __name__ == "__main__":
    main()
