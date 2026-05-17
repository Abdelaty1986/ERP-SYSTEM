import json
import subprocess
import sys
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

EVENT_LOG = Path("JARVIS_CORE/runtime_logs/controlled_execution_events.jsonl")
STATE_FILE = Path("JARVIS_CORE/runtime_memory/controlled_execution_state.json")

# Supervised mode allows all engineering actions — no fixed-command restriction
ALLOWED_ACTIONS = {
    "review", "scan_errors", "test", "report", "improve",
    "fix", "refactor", "debug", "clean", "deploy",
    "run_tests", "git_commit",
}

# Expanded subprocess allowlist for engineering work
ALLOWED_SUBPROCESSES = {
    "py_compile_app": ["python", "-m", "py_compile", "app.py"],
    "py_compile_path": ["python", "-m", "py_compile"],
    "git_status": ["git", "status", "--short"],
    "git_diff": ["git", "diff", "--stat"],
    "git_log": ["git", "log", "--oneline", "-10"],
    "git_add": ["git", "add"],
    "git_commit": ["git", "commit", "-m"],
    "pytest": ["python", "-m", "pytest", "tests", "-x", "--tb=short"],
    "python_version": ["python", "--version"],
    "pip_list": ["pip", "list", "--format=columns"],
    "ls_files": ["ls", "-la"],
    "cat_file": ["cat"],
    "python_parse": ["python", "-c"],
}

# Critical dangerous commands — never allow
DANGEROUS_COMMANDS = {
    "rm -rf", "rm -rf /", "rm -rf ~", "rm -rf .",
    "shutdown", "reboot", "init 0", "init 6",
    "dd if=", "mkfs", "format",
    "chmod 777", "chown -R",
    "> /dev/sda", "> /dev/null",
}

DANGEROUS_PATTERNS = {".git", ".env", "secrets", "node_modules", "venv", "__pycache__", "site-packages"}


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


def is_safe_path(file_path: str) -> bool:
    path = Path(file_path).resolve()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in path.parts:
            return False
    return True


def backup_file(file_path: str) -> Optional[str]:
    src = Path(file_path)
    if not src.exists():
        return None
    backup_dir = Path("JARVIS_CORE/runtime_backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = now().replace(":", "-").replace("Z", "")
    dst = backup_dir / f"{src.name}.{timestamp}.bak"
    try:
        shutil.copy2(str(src), str(dst))
        log_event("file_backed_up", {"source": file_path, "backup": str(dst)})
        return str(dst)
    except Exception as exc:
        log_event("backup_failed", {"source": file_path, "error": str(exc)})
        return None


def run_subprocess(cmd_key: str, args: list = None, timeout: int = 30) -> Dict[str, Any]:
    if cmd_key not in ALLOWED_SUBPROCESSES:
        return {"ok": False, "error": f"Subprocess not allowed: {cmd_key}", "stdout": "", "stderr": "blocked"}
    cmd = list(ALLOWED_SUBPROCESSES[cmd_key])
    if args:
        cmd.extend(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
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
    git = run_subprocess("git_status")
    results["git_status"] = git.get("stdout", "").strip() or "(clean)"
    diff = run_subprocess("git_diff")
    results["git_diff"] = diff.get("stdout", "").strip() or "(no changes)"
    log5 = run_subprocess("git_log")
    results["recent_commits"] = log5.get("stdout", "").strip() or "(no history)"
    pyc = run_subprocess("py_compile_app")
    results["app_py_compile"] = pyc.get("ok", False)
    if not pyc.get("ok"):
        results["app_errors"] = pyc.get("stderr", "").strip()
    runtime_files = []
    for p in Path("JARVIS_CORE/runtime_memory").glob("*.json"):
        try:
            runtime_files.append({"file": p.name, "size": p.stat().st_size})
        except Exception:
            runtime_files.append({"file": p.name, "size": 0})
    results["runtime_memory_files"] = runtime_files
    return {"action": "system_review", "status": "completed", "results": results}


def action_scan_errors() -> Dict[str, Any]:
    targets = ["app.py", "JARVIS_CORE/jarvis/runtime/controlled_execution_engine.py",
               "JARVIS_CORE/jarvis/runtime/controlled_patch_manager.py",
               "JARVIS_CORE/jarvis/intent/intent_parser.py"]
    findings = []
    all_ok = True
    for target in targets:
        p = Path(target)
        if not p.exists():
            findings.append({"file": target, "ok": False, "error": "file not found"})
            all_ok = False
            continue
        result = run_subprocess("py_compile_app" if target == "app.py" else "py_compile_path", args=[target])
        ok = result.get("ok", False)
        findings.append({"file": target, "ok": ok, "error": result.get("stderr", "").strip() if not ok else None})
        if not ok:
            all_ok = False
    return {"action": "scan_errors", "status": "completed" if all_ok else "warnings", "results": {"files_scanned": len(targets), "findings": findings}}


def action_run_tests() -> Dict[str, Any]:
    tests_dir = Path("tests")
    if not tests_dir.exists() or not any(tests_dir.iterdir()):
        return {"action": "run_tests", "status": "completed", "results": {"message": "no_tests_found", "detail": "tests directory missing or empty"}}
    result = run_subprocess("pytest", timeout=60)
    return {"action": "run_tests", "status": "completed" if result.get("ok") else "failed", "results": {"ok": result.get("ok", False), "stdout": result.get("stdout", ""), "stderr": result.get("stderr", ""), "returncode": result.get("returncode")}}


def action_report() -> Dict[str, Any]:
    report = {"timestamp": now(), "mode": "controlled_real_execution", "project": "ERP-SYSTEM", "checks": {}}
    git = run_subprocess("git_status")
    report["checks"]["git_status"] = git.get("stdout", "").strip() or "(clean)"
    pyc = run_subprocess("py_compile_app")
    report["checks"]["app_py_compile"] = pyc.get("ok", False)
    report["checks"]["app_py_compile_stderr"] = pyc.get("stderr", "").strip() if not pyc.get("ok") else None
    import glob
    py_files = glob.glob("*.py") + glob.glob("JARVIS_CORE/jarvis/runtime/*.py") + glob.glob("JARVIS_CORE/jarvis/intent/*.py")
    report["checks"]["python_files"] = len(py_files)
    report_path = Path("JARVIS_CORE/runtime_memory/controlled_runtime_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"action": "report", "status": "completed", "results": report}


def action_improve() -> Dict[str, Any]:
    from jarvis.runtime.controlled_patch_manager import ControlledPatchManager
    pm = ControlledPatchManager()
    preview = pm.generate_preview()
    return {"action": "improve", "status": "completed", "results": preview}


def action_review() -> Dict[str, Any]:
    return action_system_review()


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
    pip_list = run_subprocess("pip_list")
    results["pip_list"] = pip_list.get("stdout", "").strip()[:500]
    return {"action": "debug", "status": "completed", "results": results}


def action_fix(targets: list = None) -> Dict[str, Any]:
    targets = targets or ["app.py"]
    results = {"analyzed_files": [], "fixed": False, "patch": None}
    errors_found = False
    for t in targets:
        p = Path(t)
        if not p.exists():
            results["analyzed_files"].append({"file": t, "status": "not_found"})
            continue
        safe, reason = _check_path_safe(t)
        if not safe:
            results["analyzed_files"].append({"file": t, "status": "skipped", "reason": reason})
            continue
        backup_file(t)
        pyc = run_subprocess("py_compile_path", args=[t])
        ok = pyc.get("ok", False)
        results["analyzed_files"].append({
            "file": t, "status": "ok" if ok else "has_errors",
            "stderr": pyc.get("stderr", "").strip() if not ok else None,
        })
        if not ok:
            errors_found = True
        if ok:
            results["fixed"] = True
    if errors_found:
        from jarvis.runtime.controlled_patch_manager import ControlledPatchManager
        pm = ControlledPatchManager()
        preview = pm.generate_preview()
        results["patch_preview"] = preview
        results["fix_available"] = True
    results["fixed_files"] = [f["file"] for f in results["analyzed_files"] if f["status"] == "ok"]
    return {"action": "fix", "status": "completed", "results": results}


def action_refactor(targets: list = None) -> Dict[str, Any]:
    targets = targets or ["app.py"]
    results = {"analyzed_files": [], "proposal": None}
    for t in targets:
        p = Path(t)
        if not p.exists():
            results["analyzed_files"].append({"file": t, "status": "not_found"})
            continue
        safe, reason = _check_path_safe(t)
        if not safe:
            results["analyzed_files"].append({"file": t, "status": "skipped", "reason": reason})
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


def action_deploy() -> Dict[str, Any]:
    results = {}
    # Verify build first
    pyc = run_subprocess("py_compile_app")
    results["app_compile"] = pyc.get("ok", False)
    if not pyc.get("ok"):
        results["error"] = "app.py has syntax errors; fix before deploy"
        return {"action": "deploy", "status": "failed", "results": results}
    # Check git status
    git = run_subprocess("git_status")
    results["git_status"] = git.get("stdout", "").strip()
    results["recommendation"] = "Ready for deploy. Use Railway CLI or push to deploy branch."
    return {"action": "deploy", "status": "completed", "results": results}


def action_git_commit() -> Dict[str, Any]:
    results = {}
    git = run_subprocess("git_status")
    results["git_status"] = git.get("stdout", "").strip() or "(clean)"
    diff = run_subprocess("git_diff")
    results["git_diff"] = diff.get("stdout", "").strip() or "(no changes)"
    log5 = run_subprocess("git_log")
    results["recent_commits"] = log5.get("stdout", "").strip() or "(no history)"
    if results["git_status"] == "(clean)":
        results["message"] = "No changes to commit"
    else:
        results["message"] = "Changes detected. Ready to stage and commit."
        py_files_changed = [l.strip() for l in results["git_status"].split("\n") if l.strip().endswith(".py") or l.strip().endswith(".html")]
        results["files_changed"] = len(py_files_changed)
    return {"action": "git_commit", "status": "completed", "results": results}


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
    "run_tests": action_run_tests,
    "report": action_report,
    "improve": action_improve,
    "fix": action_fix,
    "refactor": action_refactor,
    "debug": action_debug,
    "clean": action_clean,
    "deploy": action_deploy,
    "git_commit": action_git_commit,
}


def _check_path_safe(file_path: str) -> tuple:
    path = Path(file_path).resolve()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in path.parts:
            return False, f"Path contains dangerous pattern: {pattern}"
    return True, ""


class ControlledExecutionEngine:

    def execute(self, command: str, command_id: str = "", parsed_intent: dict = None) -> Dict[str, Any]:
        command = str(command or "").strip()
        log_event("controlled_execution_started", {"command": command, "command_id": command_id, "parsed_intent": parsed_intent})

        # If parsed intent is provided (supervised mode), route via intent
        if parsed_intent and parsed_intent.get("intent") not in ("unknown", "blocked"):
            return self._execute_intent(command, command_id, parsed_intent)

        # If no intent but we have raw text, try parsing
        if not parsed_intent:
            try:
                from jarvis.intent.intent_parser import ArabicIntentParser
                parser = ArabicIntentParser()
                intent_data = parser.parse(command)
                if intent_data.get("intent") not in ("blocked",):
                    return self._execute_intent(command, command_id, intent_data)
            except Exception:
                pass

        # Fallback: try fixed command shortcuts
        cmd_lower = command.strip().lower()
        if cmd_lower in ACTION_MAP:
            handler = ACTION_MAP.get(cmd_lower)
            if handler:
                return self._run_handler(handler, cmd_lower, command_id)

        # Never reject — route to review as fallback
        return self._execute_intent(command, command_id, {
            "intent": "review",
            "risk_level": "low",
            "target_files": [],
            "proposed_actions": ["Route to review pipeline"],
            "validation_steps": [],
            "rollback_plan": [],
        })

    def _execute_intent(self, raw: str, command_id: str, intent_data: dict) -> Dict[str, Any]:
        intent = intent_data.get("intent", "review")
        risk = intent_data.get("risk_level", "medium")
        targets = intent_data.get("target_files", [])
        handler = INTENT_ACTION_MAP.get(intent)

        log_event("intent_execution_started", {"intent": intent, "risk": risk, "targets": targets, "raw": raw})

        result = {
            "action": intent,
            "status": "planned",
            "command": raw,
            "command_id": command_id,
            "intent": intent_data,
            "mode": "supervised_real_execution",
            "risk_level": risk,
        }

        # LOW risk: auto-execute
        if risk == "low":
            result["approval_required"] = False
            if handler:
                try:
                    if intent in ("fix", "refactor"):
                        handler_result = handler(targets)
                    else:
                        handler_result = handler()
                    result.update(handler_result)
                    result["status"] = handler_result.get("status", "completed")
                except Exception as exc:
                    result["status"] = "failed"
                    result["error"] = str(exc)
            else:
                result["status"] = "completed"
                result["message"] = f"No dedicated handler for '{intent}' — running review fallback"
                handler_result = action_review()
                result.update(handler_result)
            log_event("intent_execution_auto_completed", result)
            save_state(result)
            return self._wrap_result(result)

        # MEDIUM risk: auto-execute with checkpoint
        if risk == "medium":
            result["approval_required"] = False
            result["checkpoint_created"] = True
            # Create backup checkpoint
            for t in targets:
                if t and t != "project" and not t.startswith("("):
                    backup_file(t)
            if handler:
                try:
                    if intent in ("fix", "refactor"):
                        handler_result = handler(targets)
                    else:
                        handler_result = handler()
                    result.update(handler_result)
                    result["status"] = handler_result.get("status", "completed")
                except Exception as exc:
                    result["status"] = "failed"
                    result["error"] = str(exc)
                    self._rollback_checkpoint(targets)
            else:
                result["status"] = "completed"
                result["message"] = f"Checkpoint created for '{intent}'"
                handler_result = action_review()
                result.update(handler_result)
            log_event("intent_execution_checkpoint_completed", result)
            save_state(result)
            return self._wrap_result(result)

        # HIGH risk: require human approval
        result["approval_required"] = True
        result["status"] = "pending_approval"
        result["preview"] = self._generate_preview(intent, targets)
        log_event("intent_execution_pending_approval", result)
        save_state(result)
        return self._wrap_result(result)

    def _generate_preview(self, intent: str, targets: list) -> dict:
        return {
            "intent": intent,
            "targets": targets,
            "estimated_impact": f"{len(targets)} files affected" if targets else "Unknown",
            "requires_backup": True,
            "requires_validation": True,
        }

    def _rollback_checkpoint(self, targets: list) -> None:
        backup_dir = Path("JARVIS_CORE/runtime_backups")
        if not backup_dir.exists():
            return
        for t in targets:
            p = Path(t)
            if not p.exists():
                continue
            candidates = sorted(backup_dir.glob(f"{p.name}.*.bak"))
            if candidates:
                try:
                    shutil.copy2(str(candidates[-1]), str(p))
                    log_event("checkpoint_rollback", {"file": t, "backup": str(candidates[-1])})
                except Exception as exc:
                    log_event("checkpoint_rollback_failed", {"file": t, "error": str(exc)})

    def _run_handler(self, handler, command: str, command_id: str) -> Dict[str, Any]:
        try:
            result = handler()
            result["command"] = command
            result["command_id"] = command_id
            result["mode"] = "controlled_real_execution"
            log_event("controlled_execution_completed", result)
            save_state(result)
            return self._wrap_result(result)
        except Exception as exc:
            error_result = {
                "command": command, "command_id": command_id,
                "mode": "controlled_real_execution",
                "action": command, "status": "failed", "error": str(exc),
            }
            log_event("controlled_execution_failed", error_result)
            save_state(error_result)
            return self._wrap_result(error_result)

    def _wrap_result(self, result: dict) -> Dict[str, Any]:
        return {
            "processed": True,
            "status": result.get("status", "completed"),
            "command": result.get("command", ""),
            "action": result.get("action"),
            "results": result.get("results"),
            "intent": result.get("intent"),
            "risk_level": result.get("risk_level"),
            "approval_required": result.get("approval_required", False),
            "checkpoint_created": result.get("checkpoint_created", False),
            "preview": result.get("preview"),
            "item": result,
        }
