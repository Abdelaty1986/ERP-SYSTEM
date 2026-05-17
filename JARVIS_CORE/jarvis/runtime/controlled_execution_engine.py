import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

EVENT_LOG = Path("JARVIS_CORE/runtime_logs/controlled_execution_events.jsonl")
STATE_FILE = Path("JARVIS_CORE/runtime_memory/controlled_execution_state.json")
ALLOWED_COMMANDS = {"system_review", "scan_errors", "run_tests", "report", "improve"}

ALLOWED_SUBPROCESSES = {
    "py_compile_app": ["python", "-m", "py_compile", "app.py"],
    "py_compile_engine": ["python", "-m", "py_compile", "JARVIS_CORE/jarvis/runtime/controlled_execution_engine.py"],
    "git_status": ["git", "status", "--short"],
    "pytest": ["python", "-m", "pytest", "tests"],
}


def now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def log_event(event: str, payload: Dict[str, Any]) -> None:
    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EVENT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": now(),
            "event": event,
            "payload": payload,
        }, ensure_ascii=False) + "\n")


def save_state(state: Dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def run_subprocess(cmd_key: str, timeout: int = 30) -> Dict[str, Any]:
    if cmd_key not in ALLOWED_SUBPROCESSES:
        return {"ok": False, "error": f"Subprocess not allowed: {cmd_key}", "stdout": "", "stderr": "blocked"}
    try:
        result = subprocess.run(
            ALLOWED_SUBPROCESSES[cmd_key],
            capture_output=True, text=True, timeout=timeout
        )
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "stdout": "", "stderr": "timed out"}
    except FileNotFoundError:
        return {"ok": False, "error": "command not found", "stdout": "", "stderr": "missing binary"}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "stdout": "", "stderr": str(exc)}


def action_system_review() -> Dict[str, Any]:
    results = {}
    # Check project status
    git = run_subprocess("git_status")
    results["git_status"] = git.get("stdout", "").strip() or "(clean)"
    # Check runtime files
    runtime_files = []
    for p in Path("JARVIS_CORE/runtime_memory").glob("*.json"):
        try:
            runtime_files.append({"file": p.name, "size": p.stat().st_size})
        except Exception:
            runtime_files.append({"file": p.name, "size": 0})
    results["runtime_memory_files"] = runtime_files
    # Health summary
    results["app_py_compile"] = run_subprocess("py_compile_app").get("ok", False)
    return {
        "action": "system_review",
        "status": "completed",
        "results": results,
    }


def action_scan_errors() -> Dict[str, Any]:
    targets = ["app.py", "JARVIS_CORE/jarvis/runtime/controlled_execution_engine.py",
               "JARVIS_CORE/jarvis/runtime/controlled_patch_manager.py"]
    findings = []
    all_ok = True
    for target in targets:
        p = Path(target)
        if not p.exists():
            findings.append({"file": target, "ok": False, "error": "file not found"})
            all_ok = False
            continue
        result = run_subprocess("py_compile_app" if target == "app.py" else "py_compile_engine")
        ok = result.get("ok", False)
        findings.append({"file": target, "ok": ok, "error": result.get("stderr", "").strip() if not ok else None})
        if not ok:
            all_ok = False
    return {
        "action": "scan_errors",
        "status": "completed" if all_ok else "warnings",
        "results": {"files_scanned": len(targets), "findings": findings},
    }


def action_run_tests() -> Dict[str, Any]:
    tests_dir = Path("tests")
    if not tests_dir.exists() or not any(tests_dir.iterdir()):
        return {
            "action": "run_tests",
            "status": "completed",
            "results": {"message": "no_tests_found", "detail": "tests directory missing or empty"},
        }
    result = run_subprocess("pytest", timeout=60)
    return {
        "action": "run_tests",
        "status": "completed" if result.get("ok") else "failed",
        "results": {
            "ok": result.get("ok", False),
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "returncode": result.get("returncode"),
        },
    }


def action_report() -> Dict[str, Any]:
    report = {
        "timestamp": now(),
        "mode": "controlled_real_execution",
        "project": "ERP-SYSTEM",
        "checks": {},
    }
    git = run_subprocess("git_status")
    report["checks"]["git_status"] = git.get("stdout", "").strip() or "(clean)"
    pyc = run_subprocess("py_compile_app")
    report["checks"]["app_py_compile"] = pyc.get("ok", False)
    report["checks"]["app_py_compile_stderr"] = pyc.get("stderr", "").strip() if not pyc.get("ok") else None
    import glob
    py_files = glob.glob("*.py") + glob.glob("JARVIS_CORE/jarvis/runtime/*.py")
    report["checks"]["python_files"] = len(py_files)
    report_path = Path("JARVIS_CORE/runtime_memory/controlled_runtime_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "action": "report",
        "status": "completed",
        "results": report,
    }


def action_improve() -> Dict[str, Any]:
    from jarvis.runtime.controlled_patch_manager import ControlledPatchManager
    pm = ControlledPatchManager()
    preview = pm.generate_preview()
    return {
        "action": "improve",
        "status": "completed",
        "results": preview,
    }


ACTION_MAP = {
    "system_review": action_system_review,
    "scan_errors": action_scan_errors,
    "run_tests": action_run_tests,
    "report": action_report,
    "improve": action_improve,
}


class ControlledExecutionEngine:

    def execute(self, command: str, command_id: str = "") -> Dict[str, Any]:
        command = str(command or "").strip().lower()
        if command not in ALLOWED_COMMANDS:
            return {
                "processed": True,
                "status": "rejected",
                "command": command,
                "error": f"Command '{command}' not in allowed set",
                "action": None,
            }
        handler = ACTION_MAP.get(command)
        if not handler:
            return {
                "processed": True,
                "status": "failed",
                "command": command,
                "error": f"No handler for '{command}'",
                "action": None,
            }
        log_event("controlled_execution_started", {"command": command, "command_id": command_id})
        try:
            result = handler()
            result["command"] = command
            result["command_id"] = command_id
            result["mode"] = "controlled_real_execution"
            log_event("controlled_execution_completed", result)
            save_state(result)
            return {
                "processed": True,
                "status": result.get("status", "completed"),
                "command": command,
                "action": result.get("action"),
                "results": result.get("results"),
                "item": result,
            }
        except Exception as exc:
            error_result = {
                "command": command,
                "command_id": command_id,
                "mode": "controlled_real_execution",
                "action": command,
                "status": "failed",
                "error": str(exc),
            }
            log_event("controlled_execution_failed", error_result)
            save_state(error_result)
            return {
                "processed": True,
                "status": "failed",
                "command": command,
                "error": str(exc),
                "action": command,
            }
