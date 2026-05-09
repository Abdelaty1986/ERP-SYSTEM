import json
import os
import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT / "AI_TASKS" / "code_writer_reports"
APPLY_REPORTS_DIR = ROOT / "AI_TASKS" / "apply_reports"

BLOCKED_PARTS = [
    "database.db",
    "migrations.py",
    "modules/accounting/",
    "modules/sales/",
    "modules/inventory/",
    "auth",
    "login",
    "password",
    "posting",
    "ledger",
    "journal",
]


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def latest_code_writer_report(task_id):
    path = REPORTS_DIR / f"{task_id}_code_writer.json"
    if not path.exists():
        raise FileNotFoundError(f"Code writer report not found: {path}")
    return path


def load_plan(task_id):
    report_path = latest_code_writer_report(task_id)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    raw = report.get("raw_response", "").strip()
    return json.loads(raw), report_path


def is_safe_file(file_path):
    normalized = file_path.replace("\\", "/").lower()

    if normalized.startswith("/"):
        return False, "Absolute paths are not allowed."

    if ".." in normalized:
        return False, "Parent path traversal is not allowed."

    for blocked in BLOCKED_PARTS:
        if blocked in normalized:
            return False, f"Blocked protected area: {blocked}"

    allowed_prefixes = (
        "templates/",
        "static/css/",
        "static/js/",
        "AI_SYSTEM/",
    )

    if not normalized.startswith(allowed_prefixes):
        return False, "Only templates, static assets, and AI_SYSTEM files are allowed."

    return True, ""


def apply_line_replacements(plan):
    applied = []
    skipped = []

    if not plan.get("safe_to_apply"):
        return applied, [{"reason": "Plan safe_to_apply is not true"}]

    for change in plan.get("suggested_changes", []):
        file_path = change.get("file", "")
        safe, reason = is_safe_file(file_path)

        if not safe:
            skipped.append({"file": file_path, "reason": reason})
            continue

        full_path = ROOT / file_path

        if not full_path.exists():
            skipped.append({"file": file_path, "reason": "File does not exist"})
            continue

        text = full_path.read_text(encoding="utf-8")
        new_text = text
        file_applied = []

        diff_items = change.get("diff", [])

        if isinstance(diff_items, str):
            skipped.append({
                "file": file_path,
                "reason": "Unified/string diff is not supported. Expected list of original_line/new_line objects.",
            })
            continue

        for item in diff_items:
            if not isinstance(item, dict):
                skipped.append({"file": file_path, "reason": "Invalid diff item type"})
                continue

            original = item.get("original_line", "")
            replacement = item.get("new_line", "")

            if not original or not replacement:
                skipped.append({"file": file_path, "reason": "Invalid diff item"})
                continue

            if original not in new_text:
                skipped.append({
                    "file": file_path,
                    "reason": "Original line not found",
                    "original_line": original,
                })
                continue

            new_text = new_text.replace(original, replacement, 1)
            file_applied.append({
                "original_line": original,
                "new_line": replacement,
            })

        if file_applied and new_text != text:
            full_path.write_text(new_text, encoding="utf-8")
            applied.append({"file": file_path, "changes": file_applied})

    return applied, skipped


def run_validation():
    result = subprocess.run(
        ["python", "AI_SYSTEM/validators/validation_runner.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=900,
    )
    return {
        "returncode": result.returncode,
        "stdout_tail": (result.stdout or "")[-5000:],
        "stderr_tail": (result.stderr or "")[-5000:],
    }


def git_commit_if_needed(task_id):
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return {
            "committed": False,
            "pushed": False,
            "reason": "git is not available in Railway runtime. Patch was applied locally only."
        }

    changed = status.stdout.strip()

    if not changed:
        return {"committed": False, "reason": "No git changes detected"}

    subprocess.run(["git", "add", "."], cwd=ROOT, check=True)

    commit = subprocess.run(
        ["git", "commit", "-m", f"ai apply approved task {task_id}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    if commit.returncode != 0:
        return {
            "committed": False,
            "reason": "git commit failed",
            "stdout": commit.stdout[-3000:],
            "stderr": commit.stderr[-3000:],
        }

    push = subprocess.run(
        ["git", "push", "origin", "dev-ai"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    return {
        "committed": commit.returncode == 0,
        "pushed": push.returncode == 0,
        "commit_stdout": commit.stdout[-3000:],
        "commit_stderr": commit.stderr[-3000:],
        "push_stdout": push.stdout[-3000:],
        "push_stderr": push.stderr[-3000:],
    }


def main():
    task_id = os.environ.get("LEDGERX_APPROVED_TASK_ID", "").strip()

    if not task_id:
        raise RuntimeError("Missing LEDGERX_APPROVED_TASK_ID")

    APPLY_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    plan, source_report = load_plan(task_id)
    applied, skipped = apply_line_replacements(plan)
    validation = run_validation()

    git_result = {"skipped": True, "reason": "Validation failed or no changes applied"}

    if applied and validation["returncode"] == 0:
        git_result = git_commit_if_needed(task_id)

    final = {
        "timestamp": now(),
        "task_id": task_id,
        "source_report": str(source_report),
        "status": "APPLIED" if applied and validation["returncode"] == 0 else "NOT_APPLIED",
        "applied": applied,
        "skipped": skipped,
        "validation": validation,
        "git": git_result,
    }

    out = APPLY_REPORTS_DIR / f"{task_id}_apply_report.json"
    out.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Safe patch applier finished")
    print(out)
    print(json.dumps(final, ensure_ascii=False, indent=2))

    return final["status"] == "APPLIED"


if __name__ == "__main__":
    ok = main()
    raise SystemExit(0 if ok else 1)
