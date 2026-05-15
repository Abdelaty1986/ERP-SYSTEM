import difflib
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


class ControlledEngineeringRuntime:
    """Approval-gated patch planner and bounded file mutation runtime."""

    MAX_TASK_CHARS = 600
    MAX_HISTORY = 100
    MAX_OUTPUT_CHARS = 60000

    ENGINEERING_KEYWORDS = (
        "fix",
        "repair",
        "bug",
        "add",
        "improve",
        "solve",
        "route",
        "split",
        "module",
        "modules",
        "modularize",
        "refactor",
        "rename",
        "change",
        "ui",
        "page",
        "button",
        "label",
        "text",
        "arabic",
        "hud",
        "template",
        "app.py",
        "واجهة",
        "الواجهة",
        "واجهه",
        "الواجهه",
        "الرئيسية",
        "الرئيسيه",
        "صفحة",
        "الصفحة",
        "صفحه",
        "الصفحه",
        "زر",
        "الزر",
        "عنوان",
        "اصلح",
        "أصلح",
        "إصلاح",
        "اصلاح",
        "صحح",
        "عالج",
        "حل",
        "غيّر",
        "غير",
        "تغيير",
        "بدّل",
        "بدل",
        "أضف",
        "اضف",
        "إضافة",
        "اضافة",
        "حسّن",
        "حسن",
        "تحسين",
        "قسّم",
        "قسم",
        "تقسيم",
        "موديولات",
        "وحدات",
        "مسار",
        "راوت",
        "خطأ",
        "خطا",
        "مشكلة",
        "مشكل",
        "نص",
        "عربي",
        "العربية",
        "العربيه",
    )

    UNSAFE_KEYWORDS = (
        "delete",
        "remove database",
        "drop database",
        "drop table",
        "rm ",
        "del ",
        "erase",
        "format",
        "deploy",
        "push",
        "reset --hard",
        "checkout --",
        "secret",
        ".env",
        "database.db",
        "احذف",
        "حذف",
        "امسح",
        "مسح",
        "دمر",
        "دمّر",
        "انشر",
        "نشر",
        "قاعدة البيانات",
        "قاعدة بيانات",
    )

    ALLOWED_ROOTS = ("templates", "static", "JARVIS_CORE")
    ALLOWED_FILES = ("app.py", "jarvis_server.py")
    BLOCKED_PARTS = {
        ".git",
        "__pycache__",
        "runtime_memory",
        "runtime_logs",
        "instance",
        "venv",
        ".venv",
    }
    BLOCKED_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".env", ".pem", ".key", ".pfx"}
    BLOCKED_FILENAMES = {".env", "secret_key.txt", "database.db"}

    def __init__(self, project_root=None):
        self.project_root = Path(project_root or ".").resolve()
        self.memory_dir = self.project_root / "JARVIS_CORE" / "runtime_memory"
        self.logs_dir = self.project_root / "JARVIS_CORE" / "runtime_logs"
        self.state_path = self.memory_dir / "controlled_engineering_state.json"
        self.history_path = self.memory_dir / "controlled_engineering_history.json"
        self.events_path = self.logs_dir / "controlled_engineering_events.jsonl"

    def status(self):
        return {
            "mode": "controlled_engineering_runtime",
            "bounded": True,
            "approval_required": True,
            "unrestricted_shell_execution": False,
            "deploy_allowed": False,
            "file_deletion_allowed": False,
            "allowed_edit_paths": [
                "templates/",
                "static/",
                "JARVIS_CORE/",
                "app.py",
                "jarvis_server.py",
            ],
            "current": self.current_state(),
        }

    def classify_request(self, text):
        task = str(text or "").strip()
        lowered = task.lower()
        if not task:
            return {
                "detected_mode": "unsupported_or_unsafe",
                "reason": "Empty input cannot be planned or executed.",
            }
        if len(task) > self.MAX_TASK_CHARS:
            return {
                "detected_mode": "unsupported_or_unsafe",
                "reason": f"Input exceeds {self.MAX_TASK_CHARS} characters.",
            }
        if any(token in lowered for token in self.UNSAFE_KEYWORDS):
            return {
                "detected_mode": "unsupported_or_unsafe",
                "reason": "Unsafe or destructive request detected. JARVIS will not plan or execute it.",
            }
        if self._looks_like_safe_command(lowered):
            return {
                "detected_mode": "safe_command",
                "reason": "Input looks like a safe whitelisted command.",
            }
        if any(keyword in lowered for keyword in self.ENGINEERING_KEYWORDS):
            return {
                "detected_mode": "engineering_task",
                "reason": "Input describes a software repair or development task.",
            }
        return {
            "detected_mode": "unsupported_or_unsafe",
            "reason": "Input is neither a safe command nor a supported engineering task.",
        }

    def request_patch(self, task):
        task = str(task or "").strip()
        classification = self.classify_request(task)
        if classification["detected_mode"] != "engineering_task":
            return self.block_request(task, classification["reason"])

        plan = self._build_patch_plan(task)
        state = {
            "patch_id": str(uuid.uuid4()),
            "detected_mode": "engineering_task",
            "requested_task": task,
            "interpreted_intent": plan["interpreted_intent"],
            "files_to_modify": plan["files_to_modify"],
            "proposed_changes": plan["proposed_changes"],
            "expected_diff": plan["expected_diff"],
            "expected_change_summary": plan["expected_change_summary"],
            "risk_level": plan["risk_level"],
            "validation_plan": plan["validation_plan"],
            "rollback_plan": plan["rollback_plan"],
            "approval_required": plan["apply_supported"],
            "approval_state": "waiting_patch_approval" if plan["apply_supported"] else "planning_only",
            "apply_supported": plan["apply_supported"],
            "apply_status": "WAITING_APPROVAL" if plan["apply_supported"] else "PLANNING_ONLY",
            "safety_decision": plan["safety_decision"],
            "operations": plan["operations"],
            "rollback_checkpoint": None,
            "files_changed": [],
            "validation_result": {
                "status": "not_run",
                "steps": [],
                "stdout": "",
                "stderr": "",
            },
            "stdout": "",
            "stderr": "",
            "final_result": (
                "patch_waiting_for_approval"
                if plan["apply_supported"]
                else "patch_plan_created_without_safe_mutation_template"
            ),
            "created_at": self._now(),
            "updated_at": self._now(),
            "approved_at": None,
            "applied_at": None,
            "finished_at": None,
        }
        self._write_json(self.state_path, state)
        self._append_event(
            {
                "event": "patch_plan_requested",
                "patch_id": state["patch_id"],
                "task": task,
                "status": state["apply_status"],
                "approval_state": state["approval_state"],
            }
        )
        self._append_history(
            {
                "event": "planned",
                "patch_id": state["patch_id"],
                "requested_task": task,
                "files_changed": [],
                "approval_state": state["approval_state"],
                "result": state["final_result"],
                "validation_result": state["validation_result"],
                "timestamp": self._now(),
            }
        )
        return {
            "ok": True,
            "detected_mode": "engineering_task",
            "message": "Engineering task planned. Patch approval is required before applying.",
            "patch_state": state,
        }

    def block_request(self, task, reason):
        state = {
            "patch_id": str(uuid.uuid4()),
            "detected_mode": "unsupported_or_unsafe",
            "requested_task": str(task or "").strip(),
            "interpreted_intent": "Request blocked before patch planning.",
            "files_to_modify": [],
            "proposed_changes": [],
            "expected_diff": "",
            "expected_change_summary": reason,
            "risk_level": "blocked",
            "validation_plan": [],
            "rollback_plan": ["No file changes were made, so rollback is not required."],
            "approval_required": False,
            "approval_state": "blocked_unsafe",
            "apply_supported": False,
            "apply_status": "BLOCKED",
            "safety_decision": {
                "allowed": False,
                "reason": reason,
                "approval_required": False,
                "destructive_execution": False,
                "deploy": False,
                "file_deletion": False,
                "shell_execution": False,
            },
            "operations": [],
            "rollback_checkpoint": None,
            "files_changed": [],
            "validation_result": {
                "status": "not_run",
                "steps": [],
                "stdout": "",
                "stderr": "",
            },
            "stdout": "",
            "stderr": "",
            "final_result": "blocked_before_patch_planning",
            "created_at": self._now(),
            "updated_at": self._now(),
            "approved_at": None,
            "applied_at": None,
            "finished_at": self._now(),
        }
        self._write_json(self.state_path, state)
        self._append_event(
            {
                "event": "patch_request_blocked",
                "patch_id": state["patch_id"],
                "task": state["requested_task"],
                "status": "BLOCKED",
                "reason": reason,
            }
        )
        self._append_history(
            {
                "event": "blocked",
                "patch_id": state["patch_id"],
                "requested_task": state["requested_task"],
                "files_changed": [],
                "approval_state": "blocked_unsafe",
                "result": reason,
                "validation_result": state["validation_result"],
                "timestamp": self._now(),
            }
        )
        return {
            "ok": False,
            "detected_mode": "unsupported_or_unsafe",
            "message": reason,
            "patch_state": state,
        }

    def current_state(self):
        if not self.state_path.exists():
            return self._default_state()
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception as exc:
            state = self._default_state()
            state["apply_status"] = "FAILED"
            state["final_result"] = f"engineering_state_read_failed: {exc}"
            return state

    def approve_patch(self, patch_id=None):
        state = self.current_state()
        if not state.get("patch_id"):
            return self._failure("No patch is waiting for approval.", state)
        if patch_id and patch_id != state.get("patch_id"):
            return self._failure("Patch approval id does not match the current patch.", state)
        if state.get("approval_state") != "waiting_patch_approval":
            return self._failure("Current patch is not waiting for approval.", state)
        if not state.get("safety_decision", {}).get("allowed"):
            return self._failure("Unsafe patch plans cannot be approved.", state)
        if not state.get("apply_supported"):
            return self._failure("This plan has no deterministic safe mutation template.", state)

        now = self._now()
        state["approval_state"] = "patch_approved"
        state["apply_status"] = "APPROVED"
        state["approved_at"] = now
        state["updated_at"] = now
        state["final_result"] = "patch_approved_waiting_to_apply"
        self._write_json(self.state_path, state)
        self._append_event(
            {
                "event": "patch_approved",
                "patch_id": state["patch_id"],
                "task": state.get("requested_task"),
                "status": "APPROVED",
            }
        )
        self._append_history(
            {
                "event": "approved",
                "patch_id": state["patch_id"],
                "requested_task": state.get("requested_task"),
                "files_changed": [],
                "approval_state": state["approval_state"],
                "result": state["final_result"],
                "validation_result": state["validation_result"],
                "timestamp": now,
            }
        )
        return {"ok": True, "message": "Patch approved.", "patch_state": state}

    def reject_patch(self, patch_id=None, reason=None):
        state = self.current_state()
        if not state.get("patch_id"):
            return self._failure("No patch is available to reject.", state)
        if patch_id and patch_id != state.get("patch_id"):
            return self._failure("Patch rejection id does not match the current patch.", state)
        if state.get("apply_status") == "APPLYING":
            return self._failure("A patch that is applying cannot be rejected.", state)

        now = self._now()
        state["approval_state"] = "patch_rejected"
        state["apply_status"] = "REJECTED"
        state["updated_at"] = now
        state["finished_at"] = now
        state["final_result"] = reason or "Patch rejected by human operator."
        self._write_json(self.state_path, state)
        self._append_event(
            {
                "event": "patch_rejected",
                "patch_id": state["patch_id"],
                "task": state.get("requested_task"),
                "status": "REJECTED",
                "reason": state["final_result"],
            }
        )
        self._append_history(
            {
                "event": "rejected",
                "patch_id": state["patch_id"],
                "requested_task": state.get("requested_task"),
                "files_changed": [],
                "approval_state": state["approval_state"],
                "result": state["final_result"],
                "validation_result": state["validation_result"],
                "timestamp": now,
            }
        )
        return {"ok": True, "message": "Patch rejected.", "patch_state": state}

    def apply_approved_patch(self, patch_id=None):
        state = self.current_state()
        if not state.get("patch_id"):
            return self._failure("No patch is available to apply.", state)
        if patch_id and patch_id != state.get("patch_id"):
            return self._failure("Patch apply id does not match the current patch.", state)
        if state.get("approval_state") != "patch_approved":
            return self._failure("Patch must be approved before applying.", state)
        if state.get("apply_status") in {"APPLIED", "VALIDATION_FAILED"}:
            return self._failure("Patch has already reached a final apply state.", state)

        try:
            self._validate_operations_for_mutation(state.get("operations", []))
            checkpoint = self._create_rollback_checkpoint(state)
            changed_files = self._apply_operations(state.get("operations", []))
            validation_files = changed_files or self._operation_paths(state.get("operations", []))
            validation = self._run_validation(validation_files, state.get("operations", []))
            now = self._now()

            state["rollback_checkpoint"] = checkpoint
            state["files_changed"] = changed_files
            state["validation_result"] = validation
            state["stdout"] = validation.get("stdout", "")
            state["stderr"] = validation.get("stderr", "")
            state["applied_at"] = now
            state["finished_at"] = now
            state["updated_at"] = now
            if validation.get("status") == "passed":
                state["apply_status"] = "APPLIED"
                state["final_result"] = "Patch applied and validation passed."
            else:
                state["apply_status"] = "VALIDATION_FAILED"
                state["final_result"] = "Patch applied but validation failed. Rollback is available."

            self._write_json(self.state_path, state)
            self._append_event(
                {
                    "event": "patch_applied",
                    "patch_id": state["patch_id"],
                    "task": state.get("requested_task"),
                    "status": state["apply_status"],
                    "files_changed": changed_files,
                    "validation_status": validation.get("status"),
                }
            )
            self._append_history(
                {
                    "event": "applied",
                    "patch_id": state["patch_id"],
                    "requested_task": state.get("requested_task"),
                    "files_changed": changed_files,
                    "approval_state": state["approval_state"],
                    "result": state["final_result"],
                    "validation_result": validation,
                    "timestamp": now,
                }
            )
            return {"ok": validation.get("status") == "passed", "message": state["final_result"], "patch_state": state}
        except Exception as exc:
            now = self._now()
            state["apply_status"] = "FAILED"
            state["final_result"] = f"Patch apply failed: {exc}"
            state["stderr"] = str(exc)
            state["updated_at"] = now
            state["finished_at"] = now
            self._write_json(self.state_path, state)
            self._append_event(
                {
                    "event": "patch_apply_failed",
                    "patch_id": state.get("patch_id"),
                    "task": state.get("requested_task"),
                    "status": "FAILED",
                    "error": str(exc),
                }
            )
            return {"ok": False, "message": state["final_result"], "patch_state": state}

    def rollback_patch(self, patch_id=None):
        state = self.current_state()
        checkpoint = state.get("rollback_checkpoint") or {}
        if not checkpoint:
            return self._failure("No rollback checkpoint is available.", state)
        if patch_id and patch_id != state.get("patch_id"):
            return self._failure("Rollback patch id does not match the current patch.", state)

        restored = []
        for item in checkpoint.get("files", []):
            relative_path = item.get("path")
            path = self._resolve_mutation_path(relative_path)
            path.write_text(item.get("content", ""), encoding="utf-8")
            restored.append(relative_path)

        now = self._now()
        state["apply_status"] = "ROLLED_BACK"
        state["final_result"] = "Patch rolled back from checkpoint."
        state["updated_at"] = now
        state["finished_at"] = now
        state["files_changed"] = restored
        self._write_json(self.state_path, state)
        self._append_event(
            {
                "event": "patch_rolled_back",
                "patch_id": state.get("patch_id"),
                "files_changed": restored,
                "status": "ROLLED_BACK",
            }
        )
        self._append_history(
            {
                "event": "rolled_back",
                "patch_id": state.get("patch_id"),
                "requested_task": state.get("requested_task"),
                "files_changed": restored,
                "approval_state": state.get("approval_state"),
                "result": state["final_result"],
                "validation_result": state.get("validation_result"),
                "timestamp": now,
            }
        )
        return {"ok": True, "message": state["final_result"], "patch_state": state}

    def history(self):
        if not self.history_path.exists():
            return []
        try:
            history = json.loads(self.history_path.read_text(encoding="utf-8"))
            if isinstance(history, list):
                return history[-self.MAX_HISTORY :]
        except Exception:
            pass
        return []

    def logs(self):
        if not self.events_path.exists():
            return []
        events = []
        for line in self.events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events[-self.MAX_HISTORY :]

    def _build_patch_plan(self, task):
        lowered = task.lower()
        if "request plan" in lowered and "create patch plan" in lowered:
            return self._build_create_patch_plan_button_patch(task)
        if "engineering patch mode active" in lowered:
            return self._build_hud_label_patch_plan(task)
        return self._build_planning_only_task(task)

    def _build_create_patch_plan_button_patch(self, task):
        target = "templates/jarvis/mobile_control_center.html"
        original = self._read_project_file(target)
        updated = self._apply_create_patch_plan_button_to_text(original)
        expected_diff = self._build_diff(target, original, updated)

        return {
            "interpreted_intent": "Rename the JARVIS request planning button to Create Patch Plan.",
            "files_to_modify": [target],
            "proposed_changes": [
                "Change the visible Request Plan button label to Create Patch Plan.",
                "Keep the existing form, endpoint, approval flow, and safe command routing intact.",
                "Avoid backend shell execution, deploy, deletion, database, and secret changes.",
            ],
            "expected_change_summary": (
                "templates/jarvis/mobile_control_center.html will update the visible "
                "request button text from Request Plan to Create Patch Plan."
            ),
            "expected_diff": expected_diff,
            "risk_level": "low",
            "validation_plan": [
                "Confirm the edited template contains Create Patch Plan.",
                "Run py_compile only for modified Python files; none are expected for this patch.",
                "Record validation status, stdout, and stderr in runtime memory.",
            ],
            "rollback_plan": [
                "Create a rollback checkpoint with original template contents before applying.",
                "If validation fails, expose rollback in the HUD and keep the checkpoint available.",
                "Rollback restores the original template content from runtime memory.",
            ],
            "apply_supported": True,
            "safety_decision": {
                "allowed": True,
                "reason": (
                    "Deterministic template-only button label patch is safe to apply after approval."
                    if original != updated
                    else "The requested button label already exists; approval will re-validate the safe template state."
                ),
                "approval_required": True,
                "bounded_execution": True,
                "shell_execution": False,
                "destructive_execution": False,
                "deploy": False,
                "file_deletion": False,
            },
            "operations": [
                {
                    "type": "replace_file_text",
                    "path": target,
                    "description": "Rename the request planning button.",
                    "expected_marker": "Create Patch Plan",
                    "content": updated,
                }
            ],
        }

    def _build_hud_label_patch_plan(self, task):
        target = "templates/jarvis/mobile_control_center.html"
        original = self._read_project_file(target)
        updated = self._apply_hud_label_to_text(original)
        expected_diff = self._build_diff(target, original, updated)

        return {
            "interpreted_intent": "Add a harmless visible engineering patch mode label to the JARVIS HUD.",
            "files_to_modify": [target],
            "proposed_changes": [
                "Add a small visible HUD label with the exact text ENGINEERING PATCH MODE ACTIVE.",
                "Add scoped CSS for the label inside the existing JARVIS HUD template.",
                "Avoid backend, database, deployment, deletion, and shell changes.",
            ],
            "expected_change_summary": (
                "templates/jarvis/mobile_control_center.html will receive a scoped label "
                "near the existing approval execution console."
            ),
            "expected_diff": expected_diff,
            "risk_level": "low",
            "validation_plan": [
                "Confirm the edited template contains ENGINEERING PATCH MODE ACTIVE.",
                "Run py_compile only for modified Python files; none are expected for this patch.",
                "Record validation status, stdout, and stderr in runtime memory.",
            ],
            "rollback_plan": [
                "Create a rollback checkpoint with original file contents before applying.",
                "If validation fails, expose rollback in the HUD and keep the checkpoint available.",
                "Rollback restores the original template content from runtime memory.",
            ],
            "apply_supported": True,
            "safety_decision": {
                "allowed": True,
                "reason": (
                    "Deterministic template-only patch is safe to apply after approval."
                    if original != updated
                    else "The requested visible label already exists; approval will re-validate the safe template state."
                ),
                "approval_required": True,
                "bounded_execution": True,
                "shell_execution": False,
                "destructive_execution": False,
                "deploy": False,
                "file_deletion": False,
            },
            "operations": [
                {
                    "type": "replace_file_text",
                    "path": target,
                    "description": "Insert the engineering patch mode label and scoped CSS.",
                    "expected_marker": "ENGINEERING PATCH MODE ACTIVE",
                    "content": updated,
                }
            ],
        }

    def _build_planning_only_task(self, task):
        files = self._infer_files_for_task(task)
        return {
            "interpreted_intent": "Plan a controlled engineering change without applying a file mutation.",
            "files_to_modify": files,
            "proposed_changes": [
                "Inspect the affected UI/backend area.",
                "Prepare a bounded patch only after a deterministic safe mutation is available.",
                "Keep database, secrets, deployment, deletion, and arbitrary shell access blocked.",
            ],
            "expected_change_summary": (
                "JARVIS classified this as an engineering task and produced a planning-only patch preview. "
                "No safe deterministic edit template matched this request yet."
            ),
            "expected_diff": "No diff generated. This task requires a more specific bounded patch template.",
            "risk_level": "medium",
            "validation_plan": [
                "No file validation will run because no patch will be applied.",
                "When a deterministic patch is available, validate modified Python files with py_compile.",
            ],
            "rollback_plan": [
                "No rollback checkpoint is needed because no file changes will be made.",
            ],
            "apply_supported": False,
            "safety_decision": {
                "allowed": False,
                "reason": "Engineering task planned, but no deterministic safe mutation template matched.",
                "approval_required": False,
                "bounded_execution": True,
                "shell_execution": False,
                "destructive_execution": False,
                "deploy": False,
                "file_deletion": False,
            },
            "operations": [],
        }

    def _infer_files_for_task(self, task):
        lowered = task.lower()
        files = []
        if any(token in lowered for token in ("hud", "jarvis", "ui", "page", "button", "arabic", "text")):
            files.append("templates/jarvis/mobile_control_center.html")
        if "route" in lowered or "api" in lowered:
            files.append("app.py")
        if "style" in lowered or "css" in lowered:
            files.append("static/style.css")
        return files or ["templates/", "static/", "app.py"]

    def _apply_hud_label_to_text(self, original):
        text = original
        css_marker = ".engineering-patch-active-label"
        html_marker = "ENGINEERING PATCH MODE ACTIVE"
        if css_marker not in text:
            css = """
.engineering-patch-active-label{
  margin-top:10px;
  border:1px solid rgba(54,255,117,.48);
  border-radius:10px;
  padding:9px 12px;
  color:#dfffe8;
  background:rgba(19,76,48,.42);
  font-size:12px;
  font-weight:bold;
  letter-spacing:0;
  text-align:center;
}
"""
            anchor = ".approval-execution-console{"
            if anchor not in text:
                raise ValueError("HUD CSS anchor not found.")
            text = text.replace(anchor, css + "\n" + anchor, 1)

        if html_marker not in text:
            html = (
                '    <div class="engineering-patch-active-label" '
                'id="engineering-patch-mode-active">ENGINEERING PATCH MODE ACTIVE</div>\n\n'
            )
            anchor = '    <form class="execution-command-form" id="jarvis-execution-request-form">'
            if anchor not in text:
                raise ValueError("HUD label insertion anchor not found.")
            text = text.replace(anchor, html + anchor, 1)
        return text

    def _apply_create_patch_plan_button_to_text(self, original):
        old = '<button class="execution-button" type="submit">Request Plan</button>'
        new = '<button class="execution-button" type="submit">Create Patch Plan</button>'
        if new in original:
            return original
        if old not in original:
            raise ValueError("Request Plan button anchor not found.")
        return original.replace(old, new, 1)

    def _validate_operations_for_mutation(self, operations):
        if not operations:
            raise ValueError("No safe file mutation operations are available.")
        for operation in operations:
            if operation.get("type") != "replace_file_text":
                raise ValueError("Unsupported patch operation.")
            self._resolve_mutation_path(operation.get("path"))
            content = operation.get("content")
            if not isinstance(content, str):
                raise ValueError("Patch operation content must be text.")

    def _create_rollback_checkpoint(self, state):
        files = []
        for operation in state.get("operations", []):
            path = self._resolve_mutation_path(operation.get("path"))
            files.append(
                {
                    "path": str(path.relative_to(self.project_root)).replace("\\", "/"),
                    "content": path.read_text(encoding="utf-8"),
                }
            )
        checkpoint = {
            "checkpoint_id": str(uuid.uuid4()),
            "patch_id": state.get("patch_id"),
            "created_at": self._now(),
            "files": files,
        }
        path = self.memory_dir / f"controlled_engineering_rollback_{state.get('patch_id')}.json"
        self._write_json(path, checkpoint)
        checkpoint["path"] = str(path.relative_to(self.project_root)).replace("\\", "/")
        return checkpoint

    def _apply_operations(self, operations):
        changed = []
        for operation in operations:
            path = self._resolve_mutation_path(operation.get("path"))
            before = path.read_text(encoding="utf-8")
            after = operation.get("content", "")
            if before != after:
                path.write_text(after, encoding="utf-8")
                changed.append(str(path.relative_to(self.project_root)).replace("\\", "/"))
        return changed

    def _operation_paths(self, operations):
        paths = []
        for operation in operations:
            path = self._resolve_mutation_path(operation.get("path"))
            paths.append(str(path.relative_to(self.project_root)).replace("\\", "/"))
        return paths

    def _run_validation(self, changed_files, operations=None):
        operations = operations or []
        steps = []
        stdout_parts = []
        stderr_parts = []
        status = "passed"

        for file_name in changed_files:
            if file_name.endswith(".py"):
                result = self._run_py_compile(file_name)
                steps.append(result)
                stdout_parts.append(result.get("stdout", ""))
                stderr_parts.append(result.get("stderr", ""))
                if not result.get("ok"):
                    status = "failed"

        if "app.py" in changed_files:
            result = self._run_py_compile("app.py")
            steps.append(result)
            stdout_parts.append(result.get("stdout", ""))
            stderr_parts.append(result.get("stderr", ""))
            if not result.get("ok"):
                status = "failed"

        if "templates/jarvis/mobile_control_center.html" in changed_files:
            contains_label = "ENGINEERING PATCH MODE ACTIVE" in self._read_project_file(
                "templates/jarvis/mobile_control_center.html"
            )
            result = {
                "name": "hud_label_presence",
                "command": "read templates/jarvis/mobile_control_center.html",
                "ok": contains_label,
                "returncode": 0 if contains_label else 1,
                "stdout": "ENGINEERING PATCH MODE ACTIVE found\n" if contains_label else "",
                "stderr": "" if contains_label else "ENGINEERING PATCH MODE ACTIVE not found\n",
            }
            steps.append(result)
            stdout_parts.append(result["stdout"])
            stderr_parts.append(result["stderr"])
            if not contains_label:
                status = "failed"

        for operation in operations:
            marker = operation.get("expected_marker")
            path_name = operation.get("path")
            if not marker or not path_name:
                continue
            content = self._read_project_file(path_name)
            marker_found = marker in content
            result = {
                "name": "expected_marker_presence",
                "command": f"read {path_name}",
                "ok": marker_found,
                "returncode": 0 if marker_found else 1,
                "stdout": f"{marker} found\n" if marker_found else "",
                "stderr": "" if marker_found else f"{marker} not found\n",
            }
            steps.append(result)
            stdout_parts.append(result["stdout"])
            stderr_parts.append(result["stderr"])
            if not marker_found:
                status = "failed"

        if not steps:
            steps.append(
                {
                    "name": "no_runtime_validation_needed",
                    "command": "no modified Python files",
                    "ok": True,
                    "returncode": 0,
                    "stdout": "No Python validation required for this patch.\n",
                    "stderr": "",
                }
            )
            stdout_parts.append("No Python validation required for this patch.\n")

        return {
            "status": status,
            "steps": steps,
            "stdout": self._bounded_output("".join(stdout_parts)),
            "stderr": self._bounded_output("".join(stderr_parts)),
        }

    def _run_py_compile(self, file_name):
        path = self._resolve_mutation_path(file_name)
        argv = [sys.executable, "-m", "py_compile", str(path.relative_to(self.project_root))]
        try:
            process = subprocess.run(
                argv,
                cwd=str(self.project_root),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                shell=False,
            )
            return {
                "name": "py_compile",
                "command": "python -m py_compile " + str(path.relative_to(self.project_root)),
                "ok": process.returncode == 0,
                "returncode": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr,
            }
        except Exception as exc:
            return {
                "name": "py_compile",
                "command": "python -m py_compile " + str(path.relative_to(self.project_root)),
                "ok": False,
                "returncode": None,
                "stdout": "",
                "stderr": str(exc),
            }

    def _resolve_mutation_path(self, relative_path):
        if not relative_path:
            raise ValueError("Patch path is required.")
        candidate = (self.project_root / relative_path).resolve()
        try:
            normalized = candidate.relative_to(self.project_root)
        except ValueError as exc:
            raise ValueError(f"Patch path is outside the project: {relative_path}") from exc

        parts = set(normalized.parts)
        if parts & self.BLOCKED_PARTS:
            raise ValueError(f"Patch path is blocked: {relative_path}")
        if candidate.name in self.BLOCKED_FILENAMES or candidate.suffix.lower() in self.BLOCKED_SUFFIXES:
            raise ValueError(f"Patch path is blocked by filename or suffix: {relative_path}")

        normalized_text = str(normalized).replace("\\", "/")
        allowed = (
            normalized.parts[0] in self.ALLOWED_ROOTS
            or normalized_text in self.ALLOWED_FILES
        )
        if not allowed:
            raise ValueError(f"Patch path is not in an allowed edit area: {relative_path}")
        if not candidate.exists():
            raise ValueError(f"Patch target must already exist: {relative_path}")
        if not candidate.is_file():
            raise ValueError(f"Patch target must be a file: {relative_path}")
        return candidate

    def _read_project_file(self, relative_path):
        path = self._resolve_existing_project_file(relative_path)
        return path.read_text(encoding="utf-8")

    def _resolve_existing_project_file(self, relative_path):
        candidate = (self.project_root / relative_path).resolve()
        try:
            candidate.relative_to(self.project_root)
        except ValueError as exc:
            raise ValueError(f"Path is outside the project: {relative_path}") from exc
        if not candidate.exists() or not candidate.is_file():
            raise ValueError(f"Project file does not exist: {relative_path}")
        return candidate

    def _build_diff(self, relative_path, original, updated):
        diff = difflib.unified_diff(
            original.splitlines(),
            updated.splitlines(),
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
            lineterm="",
        )
        return "\n".join(diff)

    def _looks_like_safe_command(self, lowered):
        tokens = lowered.split()
        if len(tokens) >= 2 and tokens[0] == "git" and tokens[1] in {"status", "log"}:
            return True
        if len(tokens) >= 3 and tokens[0] in {"python", "python.exe", "python3", "py"}:
            return tokens[1] == "-m" and tokens[2] == "py_compile"
        return tokens == ["gradle", "assembledebug"]

    def _default_state(self):
        return {
            "patch_id": None,
            "detected_mode": "engineering_task",
            "requested_task": "",
            "interpreted_intent": "No engineering task requested.",
            "files_to_modify": [],
            "proposed_changes": [],
            "expected_diff": "",
            "expected_change_summary": "",
            "risk_level": "none",
            "validation_plan": [],
            "rollback_plan": [],
            "approval_required": True,
            "approval_state": "waiting_for_task",
            "apply_supported": False,
            "apply_status": "IDLE",
            "safety_decision": {
                "allowed": False,
                "reason": "No engineering task has been submitted.",
                "approval_required": True,
                "bounded_execution": True,
                "shell_execution": False,
                "destructive_execution": False,
                "deploy": False,
                "file_deletion": False,
            },
            "operations": [],
            "rollback_checkpoint": None,
            "files_changed": [],
            "validation_result": {
                "status": "not_run",
                "steps": [],
                "stdout": "",
                "stderr": "",
            },
            "stdout": "",
            "stderr": "",
            "final_result": "idle",
            "created_at": None,
            "updated_at": self._now(),
            "approved_at": None,
            "applied_at": None,
            "finished_at": None,
        }

    def _failure(self, message, state):
        return {"ok": False, "message": message, "patch_state": state}

    def _append_history(self, entry):
        history = self.history()
        history.append(entry)
        self._write_json(self.history_path, history[-self.MAX_HISTORY :])

    def _append_event(self, event):
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        event = dict(event)
        event["timestamp"] = self._now()
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _write_json(self, path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _bounded_output(self, value):
        value = str(value or "")
        if len(value) <= self.MAX_OUTPUT_CHARS:
            return value
        return value[-self.MAX_OUTPUT_CHARS :]

    def _now(self):
        return datetime.now(timezone.utc).isoformat()
