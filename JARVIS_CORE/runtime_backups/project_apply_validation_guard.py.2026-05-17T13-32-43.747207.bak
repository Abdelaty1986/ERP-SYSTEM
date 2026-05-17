
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ROOT.parent
MEMORY = ROOT / "runtime_memory"
APPLY_STATE = MEMORY / "approved_project_apply_state.json"
VALIDATION_STATE = MEMORY / "project_apply_validation_state.json"

BOUNDED = True
DANGEROUS_AUTONOMOUS_APPLY = False


def _now():
    return datetime.now(timezone.utc).isoformat()


def _run(cmd):
    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=25,
        )
        return {
            "command": " ".join(cmd),
            "returncode": result.returncode,
            "ok": result.returncode == 0,
            "stdout": result.stdout[-3000:],
            "stderr": result.stderr[-3000:],
        }
    except Exception as e:
        return {
            "command": " ".join(cmd),
            "ok": False,
            "error": str(e),
        }


def validate_latest_project_apply():
    if not APPLY_STATE.exists():
        report = {
            "runtime": "project_apply_validation_guard",
            "state": "no_apply_state_found",
            "bounded": BOUNDED,
            "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
            "rollback_required": False,
        }
        _save(report)
        return report

    apply_state = json.loads(APPLY_STATE.read_text(encoding="utf-8"))

    checks = [
        _run(["python", "-m", "py_compile", "app.py"]),
        _run(["git", "status", "--short"]),
    ]

    validation_ok = all(c.get("ok") for c in checks)

    report = {
        "timestamp": _now(),
        "runtime": "project_apply_validation_guard",
        "bounded": BOUNDED,
        "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
        "source_apply_state": apply_state.get("state"),
        "target_file": apply_state.get("target_file"),
        "project_apply_attempted": apply_state.get("project_apply_attempted", False),
        "project_apply_allowed": apply_state.get("project_apply_allowed", False),
        "validation_ok": validation_ok,
        "rollback_required": not validation_ok,
        "state": "validated" if validation_ok else "validation_failed",
        "checks": checks,
        "governance": {
            "automatic_rollback_allowed": False,
            "manual_rollback_required_on_failure": not validation_ok,
            "no_git_commit": True,
            "no_git_push": True,
            "human_review_required": True,
        },
    }

    _save(report)
    return report


def get_project_apply_validation_state():
    if not VALIDATION_STATE.exists():
        return {
            "runtime": "project_apply_validation_guard",
            "state": "not_run",
            "bounded": BOUNDED,
            "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
            "rollback_required": False,
        }

    return json.loads(VALIDATION_STATE.read_text(encoding="utf-8"))


def _save(report):
    MEMORY.mkdir(parents=True, exist_ok=True)
    VALIDATION_STATE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
