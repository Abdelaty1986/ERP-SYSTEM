
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ROOT.parent
MEMORY = ROOT / "runtime_memory"
READINESS_FILE = MEMORY / "self_development_readiness.json"

BOUNDED = True
DANGEROUS_AUTONOMOUS_APPLY = False

SAFE_COMMANDS = {
    "git_status": ["git", "status", "--short"],
    "compile_app": ["python", "-m", "py_compile", "app.py"],
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _run_safe_command(name):
    cmd = SAFE_COMMANDS[name]

    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=20,
        )

        return {
            "name": name,
            "command": " ".join(cmd),
            "returncode": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
            "ok": result.returncode == 0,
        }

    except Exception as e:
        return {
            "name": name,
            "command": " ".join(cmd),
            "ok": False,
            "error": str(e),
        }


def run_self_development_readiness():
    checks = [
        _run_safe_command("git_status"),
        _run_safe_command("compile_app"),
    ]

    report = {
        "timestamp": _now(),
        "runtime": "self_development_readiness",
        "bounded": BOUNDED,
        "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
        "execution_mode": "safe_diagnostics_only",
        "direct_file_mutation_allowed": False,
        "autonomous_apply_allowed": False,
        "human_approval_required_before_apply": True,
        "readiness_state": "prepared_not_unlocked",
        "checks": checks,
        "approval_contract": {
            "can_generate_patch": True,
            "can_apply_patch_without_human": False,
            "can_delete_files": False,
            "can_commit_without_human": False,
            "can_push_without_human": False,
            "must_compile_after_patch": True,
            "must_runtime_test_after_patch": True,
            "must_rollback_on_failure": True,
        },
    }

    MEMORY.mkdir(parents=True, exist_ok=True)
    READINESS_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return report


def get_self_development_readiness():
    if not READINESS_FILE.exists():
        return {
            "runtime": "self_development_readiness",
            "state": "not_checked",
            "bounded": BOUNDED,
            "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
        }

    return json.loads(
        READINESS_FILE.read_text(encoding="utf-8")
    )
