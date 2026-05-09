import json
import os
import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APPROVED_DIR = ROOT / "AI_TASKS" / "approved"
EXECUTION_REPORTS_DIR = ROOT / "AI_TASKS" / "execution_reports"
PATCH_PLANS_DIR = ROOT / "AI_TASKS" / "patch_plans"

PROTECTED_PATHS = [
    "database.db",
    "migrations.py",
    "modules/accounting/",
    "modules/sales/",
    "modules/inventory/",
    "posting",
    "ledger",
    "journal",
]


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def read_task(task_id):
    path = APPROVED_DIR / f"{task_id}.md"
    if not path.exists():
        raise FileNotFoundError(f"Approved task not found: {path}")
    return path.read_text(encoding="utf-8")


def is_safe_task(task_text):
    lowered = task_text.lower()
    blocked_hits = []

    for item in PROTECTED_PATHS:
        if item.lower() in lowered:
            blocked_hits.append(item)

    return len(blocked_hits) == 0, blocked_hits


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


def build_execution_report(task_id):
    EXECUTION_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    task_text = read_task(task_id)
    safe, blocked_hits = is_safe_task(task_text)

    report = {
        "timestamp": now(),
        "task_id": task_id,
        "mode": "SAFE_APPROVED_EXECUTOR_V1",
        "branch_policy": "dev-ai only",
        "main_branch_allowed": False,
        "task_safe": safe,
        "blocked_hits": blocked_hits,
        "status": "BLOCKED_BY_GUARD" if not safe else "READY_FOR_CODE_WRITER",
        "note": (
            "Executor base is active. Next phase requires GEMINI_API_KEY or OPENAI_API_KEY "
            "to generate and apply code changes safely."
        ),
    }

    if safe:
        report["validation"] = run_validation()

        env = os.environ.copy()
        env["LEDGERX_APPROVED_TASK_ID"] = task_id

        code_writer = subprocess.run(
            ["python", "AI_SYSTEM/execution_engine/code_writer.py"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=900,
        )

        report["code_writer"] = {
            "returncode": code_writer.returncode,
            "stdout_tail": (code_writer.stdout or "")[-5000:],
            "stderr_tail": (code_writer.stderr or "")[-5000:],
        }

        if code_writer.returncode != 0:
            report["status"] = "CODE_WRITER_FAILED"
        else:
            report["status"] = "CODE_PLAN_READY"

    out = EXECUTION_REPORTS_DIR / f"{task_id}_execution_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report, out


def main():
    task_id = os.environ.get("LEDGERX_APPROVED_TASK_ID", "").strip()
    if not task_id:
        raise RuntimeError("Missing LEDGERX_APPROVED_TASK_ID")

    report, path = build_execution_report(task_id)

    print("Approved executor finished")
    print(path)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    return report["status"] != "BLOCKED_BY_GUARD"


if __name__ == "__main__":
    ok = main()
    raise SystemExit(0 if ok else 1)
