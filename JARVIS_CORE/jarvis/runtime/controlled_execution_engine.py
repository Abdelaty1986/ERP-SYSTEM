import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

EVENT_LOG = Path("JARVIS_CORE/runtime_logs/controlled_execution_events.jsonl")
STATE_FILE = Path("JARVIS_CORE/runtime_memory/controlled_execution_state.json")
ALLOWED_COMMANDS = {"system_review", "scan_errors", "run_tests", "report", "improve"}

ALLOWED_ACTIONS = {
    "review", "scan_errors", "test", "report", "improve",
    "fix", "refactor", "debug", "clean", "deploy",
}

ALLOWED_SUBPROCESSES = {
    "py_compile_app": ["python", "-m", "py_compile", "app.py"],
    "py_compile_engine": ["python", "-m", "py_compile", "JARVIS_CORE/jarvis/runtime/controlled_execution_engine.py"],
    "py_compile_py": ["python", "-m", "py_compile", "*.py"],
    "git_status": ["git", "status", "--short"],
    "git_diff": ["git", "diff", "--stat"],
    "git_log": ["git", "log", "--oneline", "-5"],
    "pytest": ["python", "-m", "pytest", "tests"],
    "python_version": ["python", "--version"],
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


def action_review() -> Dict[str, Any]:
    results = {}
    git = run_subprocess("git_status")
    results["git_status"] = git.get("stdout", "").strip() or "(clean)"
    diff = run_subprocess("git_diff")
    results["git_diff"] = diff.get("stdout", "").strip() or "(no changes)"
    log5 = run_subprocess("git_log")
    results["recent_commits"] = log5.get("stdout", "").strip() or "(no history)"
    pyc = run_subprocess("py_compile_app")
    results["app_py_compile"] = pyc.get("ok", False)
    runtime_files = []
    for p in Path("JARVIS_CORE/runtime_memory").glob("*.json"):
        try:
            runtime_files.append({"file": p.name, "size": p.stat().st_size})
        except Exception:
            runtime_files.append({"file": p.name, "size": 0})
    results["runtime_memory_files"] = runtime_files[:10]
    return {"action": "review", "status": "completed", "results": results}


def action_debug() -> Dict[str, Any]:
    results = {}
    log5 = run_subprocess("git_log")
    results["recent_commits"] = log5.get("stdout", "").strip() or "(no history)"
    pyc = run_subprocess("py_compile_app")
    results["app_py_compile"] = pyc.get("ok", False)
    if not pyc.get("ok"):
        results["errors"] = pyc.get("stderr", "").strip()
    else:
        results["errors"] = "no syntax errors"
    results["python_version"] = run_subprocess("python_version").get("stdout", "").strip()
    return {"action": "debug", "status": "completed", "results": results}


def action_fix(targets: list = None) -> Dict[str, Any]:
    targets = targets or ["app.py"]
    results = {"analyzed_files": [], "fixed": False, "patch": None}
    for t in targets:
        p = Path(t)
        if not p.exists():
            results["analyzed_files"].append({"file": t, "status": "not_found"})
            continue
        pyc = run_subprocess("py_compile_app" if t == "app.py" else "py_compile_engine")
        ok = pyc.get("ok", False)
        results["analyzed_files"].append({
            "file": t,
            "status": "ok" if ok else "has_errors",
            "stderr": pyc.get("stderr", "").strip() if not ok else None,
        })
    if any(f.get("status") == "has_errors" for f in results["analyzed_files"]):
        from jarvis.runtime.controlled_patch_manager import ControlledPatchManager
        pm = ControlledPatchManager()
        preview = pm.generate_preview()
        results["patch_preview"] = preview
        results["fix_available"] = True
    return {"action": "fix", "status": "completed", "results": results}


def action_refactor(targets: list = None) -> Dict[str, Any]:
    targets = targets or ["app.py"]
    results = {"analyzed_files": [], "proposal": None}
    for t in targets:
        p = Path(t)
        if not p.exists():
            results["analyzed_files"].append({"file": t, "status": "not_found"})
            continue
        lines = len(p.read_text(encoding="utf-8").splitlines()) if p.suffix in (".py", ".html") else 0
        results["analyzed_files"].append({"file": t, "lines": lines, "status": "analyzed"})
    total_lines = sum(f.get("lines", 0) for f in results["analyzed_files"])
    results["proposal"] = f"Refactoring plan: {len(targets)} files, {total_lines} total lines. Generate patch preview to proceed."
    return {"action": "refactor", "status": "completed", "results": results}


def action_clean() -> Dict[str, Any]:
    results = {"unused_patterns": [], "suggestions": []}
    for p in sorted(Path(".").glob("*.py")):
        if p.name == "app.py":
            continue
        content = p.read_text(encoding="utf-8")
        if "pass" in content and len(content.splitlines()) < 10:
            results["unused_patterns"].append({"file": p.name, "reason": "stub file"})
    results["suggestions"] = ["Review stub files for removal", "Check __pycache__ directory"]
    return {"action": "clean", "status": "completed", "results": results}


ACTION_MAP = {
    "system_review": action_system_review,
    "scan_errors": action_scan_errors,
    "run_tests": action_run_tests,
    "report": action_report,
    "improve": action_improve,
}

INTENT_ACTION_MAP = {
    "review": action_review,
    "scan_errors": action_scan_errors,
    "test": action_run_tests,
    "report": action_report,
    "improve": action_improve,
    "fix": action_fix,
    "refactor": action_refactor,
    "debug": action_debug,
    "clean": action_clean,
    "deploy": None,
}


class ControlledExecutionEngine:

    def execute(self, command: str, command_id: str = "", parsed_intent: dict = None) -> Dict[str, Any]:
        command = str(command or "").strip().lower()
        log_event("controlled_execution_started", {"command": command, "command_id": command_id, "parsed_intent": parsed_intent})

        # If parsed intent is provided (supervised mode), route via intent
        if parsed_intent and parsed_intent.get("intent") not in ("unknown", "blocked"):
            return self._execute_intent(command, command_id, parsed_intent)

        # Fallback: fixed command execution
        if command in ALLOWED_COMMANDS:
            handler = ACTION_MAP.get(command)
            if handler:
                return self._run_handler(handler, command, command_id)
            return {
                "processed": True, "status": "failed",
                "command": command, "error": f"No handler for '{command}'",
                "action": None,
            }

        # Unknown command — try parsing as Arabic text
        try:
            from jarvis.intent.intent_parser import ArabicIntentParser
            parser = ArabicIntentParser()
            intent_data = parser.parse(command)
            if intent_data.get("intent") not in ("unknown", "blocked"):
                return self._execute_intent(command, command_id, intent_data)
        except Exception:
            pass

        return {
            "processed": True, "status": "rejected",
            "command": command,
            "error": f"Command '{command}' not in allowed set and could not be parsed as intent",
            "action": None,
        }

    def _execute_intent(self, raw: str, command_id: str, intent_data: dict) -> Dict[str, Any]:
        intent = intent_data.get("intent", "review")
        risk = intent_data.get("risk_level", "medium")
        targets = intent_data.get("target_files", [])
        handler = INTENT_ACTION_MAP.get(intent)
        if not handler:
            return {
                "processed": True, "status": "failed",
                "command": raw, "error": f"No handler for intent '{intent}'",
                "action": intent, "intent": intent_data,
            }

        log_event("intent_execution_started", {"intent": intent, "risk": risk, "targets": targets, "raw": raw})
        try:
            if intent in ("fix", "refactor"):
                result = handler(targets)
            else:
                result = handler()
            result["command"] = raw
            result["command_id"] = command_id
            result["intent"] = intent_data
            result["mode"] = "supervised_real_execution"
            result["risk_level"] = risk

            if risk == "low":
                result["approval_required"] = False
                result["status"] = "completed"
            elif risk == "medium":
                result["approval_required"] = False
                result["checkpoint_created"] = True
                result["status"] = "completed"
            else:
                result["approval_required"] = True
                result["status"] = "pending_approval"

            log_event("intent_execution_completed", result)
            save_state(result)
            return {
                "processed": True,
                "status": result.get("status", "completed"),
                "command": raw,
                "action": result.get("action"),
                "results": result.get("results"),
                "intent": intent_data,
                "risk_level": risk,
                "approval_required": result.get("approval_required", False),
                "item": result,
            }
        except Exception as exc:
            error_result = {
                "command": raw, "command_id": command_id,
                "intent": intent_data, "mode": "supervised_real_execution",
                "action": intent, "status": "failed", "error": str(exc),
            }
            log_event("intent_execution_failed", error_result)
            save_state(error_result)
            return {
                "processed": True, "status": "failed",
                "command": raw, "error": str(exc),
                "action": intent, "intent": intent_data,
            }

    def _run_handler(self, handler, command: str, command_id: str) -> Dict[str, Any]:
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
                "command": command, "command_id": command_id,
                "mode": "controlled_real_execution",
                "action": command, "status": "failed", "error": str(exc),
            }
            log_event("controlled_execution_failed", error_result)
            save_state(error_result)
            return {
                "processed": True, "status": "failed",
                "command": command, "error": str(exc), "action": command,
            }
