import json
import os
import shlex
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


class ApprovalDrivenExecutionRuntime:
    """Bounded, approval-gated command runner for the JARVIS HUD."""

    MAX_COMMAND_CHARS = 240
    MAX_OUTPUT_CHARS = 60000
    MAX_HISTORY = 100

    FORBIDDEN_FRAGMENTS = (
        "|",
        "&",
        ";",
        ">",
        "<",
        "`",
        "$(",
        "\n",
        "\r",
        "\x00",
    )

    GIT_STATUS_FLAGS = {
        "-s",
        "-b",
        "-uno",
        "-unormal",
        "-uall",
        "--short",
        "--branch",
        "--porcelain",
        "--porcelain=v1",
        "--porcelain=v2",
        "--untracked-files=no",
        "--untracked-files=normal",
        "--untracked-files=all",
        "--ignored=no",
        "--ignored=matching",
        "--ignored=traditional",
        "--ahead-behind",
        "--no-ahead-behind",
    }

    GIT_LOG_FLAGS = {
        "--oneline",
        "--decorate",
        "--decorate=short",
        "--decorate=full",
        "--graph",
        "--name-only",
        "--no-name-only",
        "--stat",
        "--no-stat",
    }

    def __init__(self, project_root=None):
        self.project_root = Path(project_root or ".").resolve()
        self.memory_dir = self.project_root / "JARVIS_CORE" / "runtime_memory"
        self.logs_dir = self.project_root / "JARVIS_CORE" / "runtime_logs"
        self.state_path = self.memory_dir / "approval_execution_state.json"
        self.history_path = self.memory_dir / "approval_execution_history.json"
        self.events_path = self.logs_dir / "approval_execution_events.jsonl"
        self._lock = threading.RLock()
        self._active_threads = {}

    def status(self):
        state = self.current_state()
        return {
            "mode": "approval_driven_execution",
            "bounded": True,
            "dangerous_execution": False,
            "deploy_allowed": False,
            "file_deletion_allowed": False,
            "shell_execution_allowed": False,
            "approval_required_for_real_execution": True,
            "whitelist": [
                "git status",
                "git log",
                "python -m py_compile",
                "gradle assembleDebug",
            ],
            "states": [
                "IDLE",
                "WAITING_APPROVAL",
                "APPROVED",
                "EXECUTING",
                "COMPLETED",
                "FAILED",
                "TIMED_OUT",
                "REJECTED",
                "BLOCKED",
            ],
            "current": state,
        }

    def request_execution(self, command):
        command = str(command or "").strip()
        analysis = self._analyze(command)
        request_id = str(uuid.uuid4())

        state = {
            "request_id": request_id,
            "detected_mode": "safe_command",
            "requested_command": command,
            "approved_command": None,
            "interpreted_action": analysis["interpreted_action"],
            "execution_plan": analysis["execution_plan"],
            "risk_analysis": analysis["risk_analysis"],
            "risk_level": analysis["risk_level"],
            "approval_required": bool(analysis["safe"]),
            "approval_state": "waiting_approval" if analysis["safe"] else "blocked_unsafe",
            "execution_status": "WAITING_APPROVAL" if analysis["safe"] else "BLOCKED",
            "safety_decision": analysis["safety_decision"],
            "matched_whitelist": analysis.get("matched_whitelist"),
            "actual_argv": analysis.get("actual_argv", []),
            "display_argv": analysis.get("display_argv", []),
            "timeout_seconds": analysis.get("timeout_seconds"),
            "cwd": str(self.project_root),
            "stdout": "",
            "stderr": "",
            "returncode": None,
            "final_result": "waiting_for_approval" if analysis["safe"] else "blocked_before_approval",
            "created_at": self._now(),
            "updated_at": self._now(),
            "approved_at": None,
            "started_at": None,
            "finished_at": None,
        }

        with self._lock:
            self._write_json(self.state_path, state)
            self._append_event_locked(
                {
                    "event": "execution_requested",
                    "request_id": request_id,
                    "command": command,
                    "status": state["execution_status"],
                    "approval_state": state["approval_state"],
                    "safe": analysis["safe"],
                    "reason": analysis["safety_decision"]["reason"],
                }
            )
            self._append_history_locked(
                {
                    "event": "request",
                    "request_id": request_id,
                    "command": command,
                    "status": state["execution_status"],
                    "approval_state": state["approval_state"],
                    "risk_level": state["risk_level"],
                    "result": state["final_result"],
                    "reason": analysis["safety_decision"]["reason"],
                    "timestamp": self._now(),
                }
            )

        return {
            "ok": analysis["safe"],
            "message": (
                "Command accepted for approval."
                if analysis["safe"]
                else "Command blocked by the safety gate."
            ),
            "state": state,
        }

    def current_state(self):
        with self._lock:
            if not self.state_path.exists():
                return self._default_state()

            try:
                state = json.loads(self.state_path.read_text(encoding="utf-8"))
            except Exception as exc:
                state = self._default_state()
                state["execution_status"] = "FAILED"
                state["final_result"] = f"state_read_failed: {exc}"
                return state

            return self._normalize_state_mode(state)

    def current_plan(self):
        state = self.current_state()
        return {
            "request_id": state.get("request_id"),
            "requested_command": state.get("requested_command"),
            "interpreted_action": state.get("interpreted_action"),
            "execution_plan": state.get("execution_plan", []),
            "risk_analysis": state.get("risk_analysis", []),
            "risk_level": state.get("risk_level"),
            "approval_required": state.get("approval_required"),
            "approval_state": state.get("approval_state"),
            "safety_decision": state.get("safety_decision", {}),
            "matched_whitelist": state.get("matched_whitelist"),
            "actual_argv": state.get("display_argv") or state.get("actual_argv", []),
        }

    def clear_for_engineering_task(self, task="", patch_id=None):
        state = self._default_state()
        state.update(
            {
                "request_id": None,
                "detected_mode": "engineering_task",
                "requested_command": str(task or "").strip(),
                "approved_command": None,
                "interpreted_action": "Engineering task routed to controlled patch planning.",
                "execution_plan": [
                    "Classify input before shell handling.",
                    "Route engineering work to the controlled patch planner.",
                    "Keep shell execution disabled for this request.",
                    "Use patch approval controls before any file mutation.",
                ],
                "risk_analysis": [
                    "No shell command was prepared.",
                    "Shell whitelist is only used for real safe commands.",
                    "Patch approval is required before bounded file edits.",
                ],
                "risk_level": "low",
                "approval_required": True,
                "approval_state": "superseded_by_patch_approval",
                "execution_status": "WAITING_APPROVAL",
                "safety_decision": {
                    "allowed": False,
                    "reason": "Engineering task is handled by controlled patch planning, not shell execution.",
                    "approval_required": True,
                    "bounded_execution": True,
                    "shell_execution": False,
                    "destructive_execution": False,
                    "deploy": False,
                    "file_deletion": False,
                },
                "final_result": "no_shell_execution_for_engineering_task",
                "updated_at": self._now(),
            }
        )
        self._write_json(self.state_path, state)
        self._append_event_locked(
            {
                "event": "execution_state_cleared_for_engineering_task",
                "request_id": None,
                "patch_id": patch_id,
                "command": task,
                "status": "IDLE",
            }
        )
        return state

    def clear_for_blocked_request(self, command="", reason="Request is unsupported or unsafe."):
        block_reason = str(reason or "Request is unsupported or unsafe.")
        state = self._default_state()
        state.update(
            {
                "request_id": None,
                "detected_mode": "unsupported_or_unsafe",
                "requested_command": str(command or "").strip(),
                "approved_command": None,
                "interpreted_action": "Request blocked before shell or patch planning.",
                "execution_plan": [
                    "Classify the input before execution.",
                    "Block unsafe or unsupported intent.",
                    "Do not prepare shell execution or file mutation.",
                ],
                "risk_analysis": [
                    block_reason,
                    "No approval path is available for blocked requests.",
                    "No files were modified and no shell command was executed.",
                ],
                "risk_level": "blocked",
                "approval_required": False,
                "approval_state": "blocked_unsafe",
                "execution_status": "BLOCKED",
                "safety_decision": {
                    "allowed": False,
                    "reason": block_reason,
                    "approval_required": False,
                    "bounded_execution": True,
                    "shell_execution": False,
                    "destructive_execution": False,
                    "deploy": False,
                    "file_deletion": False,
                },
                "stdout": "",
                "stderr": "",
                "returncode": None,
                "final_result": "blocked_before_approval",
                "created_at": self._now(),
                "updated_at": self._now(),
            }
        )
        self._write_json(self.state_path, state)
        self._append_event_locked(
            {
                "event": "request_blocked_before_execution",
                "request_id": None,
                "command": command,
                "status": "BLOCKED",
                "reason": block_reason,
            }
        )
        self._append_history_locked(
            {
                "event": "blocked",
                "request_id": None,
                "command": command,
                "status": "BLOCKED",
                "approval_state": "blocked_unsafe",
                "risk_level": "blocked",
                "result": "blocked_before_approval",
                "reason": block_reason,
                "timestamp": self._now(),
            }
        )
        return state

    def approve_execution(self, request_id=None):
        with self._lock:
            state = self.current_state()
            if not state.get("request_id"):
                return self._failure("No command is waiting for approval.", state)
            if request_id and request_id != state.get("request_id"):
                return self._failure("Approval request id does not match the current command.", state)
            if not state.get("safety_decision", {}).get("allowed"):
                return self._failure("Unsafe commands cannot be approved.", state)
            if state.get("approval_state") != "waiting_approval":
                return self._failure("Current command is not waiting for approval.", state)
            if state.get("execution_status") == "EXECUTING":
                return self._failure("Current command is already executing.", state)

            now = self._now()
            state["approval_state"] = "approved"
            state["approved_command"] = state.get("requested_command")
            state["execution_status"] = "APPROVED"
            state["final_result"] = "approved_waiting_to_run"
            state["approved_at"] = now
            state["updated_at"] = now
            self._write_json(self.state_path, state)
            self._append_event_locked(
                {
                    "event": "execution_approved",
                    "request_id": state["request_id"],
                    "command": state.get("requested_command"),
                    "status": "APPROVED",
                }
            )
            self._append_history_locked(
                {
                    "event": "approved",
                    "request_id": state["request_id"],
                    "command": state.get("requested_command"),
                    "status": "APPROVED",
                    "approval_state": "approved",
                    "result": "approved_waiting_to_run",
                    "timestamp": now,
                }
            )
            return {"ok": True, "message": "Command approved.", "state": state}

    def reject_execution(self, request_id=None, reason=None):
        with self._lock:
            state = self.current_state()
            if not state.get("request_id"):
                return self._failure("No command is available to reject.", state)
            if request_id and request_id != state.get("request_id"):
                return self._failure("Reject request id does not match the current command.", state)
            if state.get("execution_status") == "EXECUTING":
                return self._failure("An executing command cannot be rejected.", state)

            now = self._now()
            reject_reason = reason or "Rejected by human operator."
            state["approval_state"] = "rejected"
            state["execution_status"] = "REJECTED"
            state["final_result"] = reject_reason
            state["updated_at"] = now
            state["finished_at"] = now
            self._write_json(self.state_path, state)
            self._append_event_locked(
                {
                    "event": "execution_rejected",
                    "request_id": state["request_id"],
                    "command": state.get("requested_command"),
                    "status": "REJECTED",
                    "reason": reject_reason,
                }
            )
            self._append_history_locked(
                {
                    "event": "rejected",
                    "request_id": state["request_id"],
                    "command": state.get("requested_command"),
                    "status": "REJECTED",
                    "approval_state": "rejected",
                    "result": reject_reason,
                    "timestamp": now,
                }
            )
            return {"ok": True, "message": "Command rejected.", "state": state}

    def run_approved_execution(self, request_id=None):
        with self._lock:
            state = self.current_state()
            if not state.get("request_id"):
                return self._failure("No command is available to run.", state)
            if request_id and request_id != state.get("request_id"):
                return self._failure("Run request id does not match the current command.", state)
            if state.get("approval_state") != "approved":
                return self._failure("Command must be approved before it can run.", state)
            if not state.get("safety_decision", {}).get("allowed"):
                return self._failure("Safety gate blocked this command.", state)
            if state.get("execution_status") == "EXECUTING":
                return {"ok": True, "message": "Command is already executing.", "state": state}
            if state.get("execution_status") in {"COMPLETED", "FAILED", "TIMED_OUT"}:
                return self._failure("Command already reached a final execution state.", state)

            now = self._now()
            state["execution_status"] = "EXECUTING"
            state["final_result"] = "running"
            state["stdout"] = ""
            state["stderr"] = ""
            state["returncode"] = None
            state["started_at"] = now
            state["updated_at"] = now
            self._write_json(self.state_path, state)
            self._append_event_locked(
                {
                    "event": "execution_started",
                    "request_id": state["request_id"],
                    "command": state.get("requested_command"),
                    "status": "EXECUTING",
                }
            )

            thread = threading.Thread(
                target=self._execute_request,
                args=(state["request_id"],),
                daemon=True,
            )
            self._active_threads[state["request_id"]] = thread
            thread.start()

            return {"ok": True, "message": "Approved command started.", "state": state}

    def history(self):
        with self._lock:
            return self._read_history_locked()

    def logs(self):
        with self._lock:
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

    def _execute_request(self, request_id):
        with self._lock:
            state = self.current_state()
            if state.get("request_id") != request_id:
                return
            argv = list(state.get("actual_argv") or [])
            timeout_seconds = int(state.get("timeout_seconds") or 30)

        final_status = "FAILED"
        final_result = "execution_failed"
        returncode = None
        timed_out = False

        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["GIT_OPTIONAL_LOCKS"] = "0"
            process = subprocess.Popen(
                argv,
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                env=env,
            )

            stdout_thread = threading.Thread(
                target=self._read_stream,
                args=(request_id, process.stdout, "stdout"),
                daemon=True,
            )
            stderr_thread = threading.Thread(
                target=self._read_stream,
                args=(request_id, process.stderr, "stderr"),
                daemon=True,
            )
            stdout_thread.start()
            stderr_thread.start()

            started = time.monotonic()
            while process.poll() is None:
                if time.monotonic() - started > timeout_seconds:
                    timed_out = True
                    process.kill()
                    break
                time.sleep(0.2)

            returncode = process.wait()
            stdout_thread.join(timeout=2)
            stderr_thread.join(timeout=2)

            if timed_out:
                final_status = "TIMED_OUT"
                final_result = f"Command exceeded {timeout_seconds} seconds and was terminated."
            elif returncode == 0:
                final_status = "COMPLETED"
                final_result = "Command completed successfully."
            else:
                final_status = "FAILED"
                final_result = f"Command exited with return code {returncode}."
        except FileNotFoundError as exc:
            returncode = None
            final_status = "FAILED"
            final_result = f"Executable not found: {exc.filename}"
            self._append_output(request_id, "stderr", final_result + "\n")
        except Exception as exc:
            returncode = None
            final_status = "FAILED"
            final_result = f"Execution failed: {exc}"
            self._append_output(request_id, "stderr", final_result + "\n")

        with self._lock:
            state = self.current_state()
            if state.get("request_id") == request_id:
                now = self._now()
                state["execution_status"] = final_status
                state["returncode"] = returncode
                state["final_result"] = final_result
                state["finished_at"] = now
                state["updated_at"] = now
                self._write_json(self.state_path, state)
                self._append_event_locked(
                    {
                        "event": "execution_finished",
                        "request_id": request_id,
                        "command": state.get("requested_command"),
                        "status": final_status,
                        "returncode": returncode,
                        "result": final_result,
                    }
                )
                self._append_history_locked(
                    {
                        "event": "finished",
                        "request_id": request_id,
                        "command": state.get("requested_command"),
                        "status": final_status,
                        "approval_state": state.get("approval_state"),
                        "returncode": returncode,
                        "result": final_result,
                        "stdout": state.get("stdout", ""),
                        "stderr": state.get("stderr", ""),
                        "timestamp": now,
                    }
                )
            self._active_threads.pop(request_id, None)

    def _read_stream(self, request_id, stream, key):
        if stream is None:
            return
        try:
            for line in iter(stream.readline, ""):
                if not line:
                    break
                self._append_output(request_id, key, line)
        finally:
            stream.close()

    def _append_output(self, request_id, key, chunk):
        with self._lock:
            state = self.current_state()
            if state.get("request_id") != request_id:
                return
            state[key] = self._bounded_output(str(state.get(key, "")) + str(chunk or ""))
            state["updated_at"] = self._now()
            self._write_json(self.state_path, state)

    def _analyze(self, command):
        parsed = self._parse_command(command)
        if not parsed["ok"]:
            return self._blocked_analysis(command, parsed["reason"])

        tokens = parsed["tokens"]
        lowered = [token.lower() for token in tokens]

        if not tokens:
            return self._blocked_analysis(command, "Empty command.")

        if "deploy" in lowered:
            return self._blocked_analysis(command, "Deploy commands are not allowed.")

        if lowered[0] == "git" and len(lowered) >= 2 and lowered[1] == "status":
            return self._analyze_git_status(command, tokens)

        if lowered[0] == "git" and len(lowered) >= 2 and lowered[1] == "log":
            return self._analyze_git_log(command, tokens)

        if self._is_python_py_compile(lowered):
            return self._analyze_py_compile(command, tokens)

        if lowered == ["gradle", "assembledebug"]:
            return self._allowed_analysis(
                command=command,
                interpreted_action="Build the Android debug APK using Gradle assembleDebug.",
                matched_whitelist="gradle assembleDebug",
                actual_argv=["gradle", "assembleDebug"],
                display_argv=["gradle", "assembleDebug"],
                timeout_seconds=300,
                risk_level="medium",
                risk_analysis=[
                    "Allowed because it matches the Gradle debug build whitelist entry.",
                    "Bounded to 300 seconds.",
                    "Shell execution, deploy, deletion, and custom Gradle tasks are blocked.",
                    "Build outputs may be generated by Gradle inside the project build folders.",
                ],
                plan=[
                    "Confirm the command exactly matches gradle assembleDebug.",
                    "Wait for explicit human approval in the HUD approval area.",
                    "Run Gradle without a shell in the project root.",
                    "Capture stdout, stderr, return code, and final result.",
                    "Record the execution in JARVIS history.",
                ],
            )

        return self._blocked_analysis(
            command,
            "Command does not match the safe whitelist: git status, git log, python -m py_compile, gradle assembleDebug.",
        )

    def _analyze_git_status(self, command, tokens):
        extra = tokens[2:]
        for item in extra:
            if item not in self.GIT_STATUS_FLAGS:
                return self._blocked_analysis(
                    command,
                    f"git status option is not allowed: {item}",
                )

        return self._allowed_analysis(
            command=command,
            interpreted_action="Read the repository working tree status.",
            matched_whitelist="git status",
            actual_argv=tokens,
            display_argv=tokens,
            timeout_seconds=30,
            risk_level="low",
            risk_analysis=[
                "Allowed because it matches the git status whitelist entry.",
                "Only safe status flags are accepted.",
                "Shell execution is disabled and stdin is closed.",
                "GIT_OPTIONAL_LOCKS=0 is applied to reduce repository write side effects.",
            ],
            plan=[
                "Parse the command into arguments without invoking a shell.",
                "Verify the base command is git status and every option is whitelisted.",
                "Wait for explicit human approval in the HUD approval area.",
                "Run the command in the project root with a 30 second timeout.",
                "Capture stdout, stderr, return code, and final result.",
                "Record the execution in JARVIS history.",
            ],
        )

    def _analyze_git_log(self, command, tokens):
        extra = tokens[2:]
        bounded_args = list(tokens)
        has_limit = False

        for item in extra:
            lowered = item.lower()
            if lowered in self.GIT_LOG_FLAGS:
                continue
            if lowered == "-n":
                has_limit = True
                continue
            if lowered.startswith("--max-count="):
                count_text = lowered.split("=", 1)[1]
                if not count_text.isdigit() or int(count_text) > 50:
                    return self._blocked_analysis(command, "git log max-count must be between 1 and 50.")
                has_limit = True
                continue
            if lowered.startswith("-") and lowered[1:].isdigit():
                if int(lowered[1:]) > 50:
                    return self._blocked_analysis(command, "git log shorthand count must be 50 or less.")
                has_limit = True
                continue
            return self._blocked_analysis(command, f"git log option is not allowed: {item}")

        if not has_limit:
            bounded_args = tokens + ["--max-count=20"]

        return self._allowed_analysis(
            command=command,
            interpreted_action="Read recent Git commit history.",
            matched_whitelist="git log",
            actual_argv=bounded_args,
            display_argv=bounded_args,
            timeout_seconds=30,
            risk_level="low",
            risk_analysis=[
                "Allowed because it matches the git log whitelist entry.",
                "Output is bounded to at most 50 commits; default is 20 commits.",
                "Only read-only log formatting flags are accepted.",
                "Shell execution is disabled and stdin is closed.",
            ],
            plan=[
                "Parse the command into arguments without invoking a shell.",
                "Verify the base command is git log and every option is whitelisted.",
                "Apply a bounded commit limit when one is not provided.",
                "Wait for explicit human approval in the HUD approval area.",
                "Run the command in the project root with a 30 second timeout.",
                "Capture stdout, stderr, return code, and final result.",
                "Record the execution in JARVIS history.",
            ],
        )

    def _analyze_py_compile(self, command, tokens):
        files = tokens[3:]
        if not files:
            return self._blocked_analysis(command, "python -m py_compile requires at least one Python file.")

        safe_files = []
        for file_name in files:
            if file_name.startswith("-"):
                return self._blocked_analysis(command, f"py_compile options are not allowed: {file_name}")
            path = (self.project_root / file_name).resolve()
            if not self._is_inside_project(path):
                return self._blocked_analysis(command, f"Python file is outside the project: {file_name}")
            if path.suffix.lower() != ".py":
                return self._blocked_analysis(command, f"Only .py files may be compiled: {file_name}")
            safe_files.append(str(path.relative_to(self.project_root)))

        actual_argv = [sys.executable, "-m", "py_compile"] + safe_files
        display_argv = ["python", "-m", "py_compile"] + safe_files

        return self._allowed_analysis(
            command=command,
            interpreted_action="Compile Python files to validate syntax.",
            matched_whitelist="python -m py_compile",
            actual_argv=actual_argv,
            display_argv=display_argv,
            timeout_seconds=60,
            risk_level="low",
            risk_analysis=[
                "Allowed because it matches the Python py_compile whitelist entry.",
                "Only project-local .py files are accepted.",
                "The current Python interpreter is used without a shell.",
                "py_compile may generate normal __pycache__ runtime artifacts.",
            ],
            plan=[
                "Parse the command into arguments without invoking a shell.",
                "Verify python -m py_compile and validate every target is a project-local .py file.",
                "Wait for explicit human approval in the HUD approval area.",
                "Run py_compile with a 60 second timeout.",
                "Capture stdout, stderr, return code, and final result.",
                "Record the execution in JARVIS history.",
            ],
        )

    def _allowed_analysis(
        self,
        command,
        interpreted_action,
        matched_whitelist,
        actual_argv,
        display_argv,
        timeout_seconds,
        risk_level,
        risk_analysis,
        plan,
    ):
        return {
            "safe": True,
            "interpreted_action": interpreted_action,
            "execution_plan": plan,
            "risk_analysis": risk_analysis,
            "risk_level": risk_level,
            "matched_whitelist": matched_whitelist,
            "actual_argv": actual_argv,
            "display_argv": display_argv,
            "timeout_seconds": timeout_seconds,
            "safety_decision": {
                "allowed": True,
                "reason": f"Matched safe whitelist entry: {matched_whitelist}.",
                "approval_required": True,
                "bounded_execution": True,
                "shell_execution": False,
                "destructive_execution": False,
                "deploy": False,
                "file_deletion": False,
            },
        }

    def _blocked_analysis(self, command, reason):
        return {
            "safe": False,
            "interpreted_action": "Command rejected before approval.",
            "execution_plan": [
                "Parse the requested command.",
                "Compare it against the safe execution whitelist.",
                "Block execution because the command is unsafe or unsupported.",
                "Explain the rejection in the HUD and do not run anything.",
            ],
            "risk_analysis": [
                reason,
                "No approval button can unlock a command that fails the safety gate.",
                "No subprocess was started.",
            ],
            "risk_level": "blocked",
            "matched_whitelist": None,
            "actual_argv": [],
            "display_argv": [],
            "timeout_seconds": None,
            "safety_decision": {
                "allowed": False,
                "reason": reason,
                "approval_required": False,
                "bounded_execution": True,
                "shell_execution": False,
                "destructive_execution": False,
                "deploy": False,
                "file_deletion": False,
            },
        }

    def _parse_command(self, command):
        if not command:
            return {"ok": False, "reason": "Empty command.", "tokens": []}
        if len(command) > self.MAX_COMMAND_CHARS:
            return {
                "ok": False,
                "reason": f"Command exceeds {self.MAX_COMMAND_CHARS} characters.",
                "tokens": [],
            }
        for fragment in self.FORBIDDEN_FRAGMENTS:
            if fragment in command:
                return {
                    "ok": False,
                    "reason": f"Shell control token is not allowed: {fragment!r}",
                    "tokens": [],
                }
        try:
            raw_tokens = shlex.split(command, posix=False)
        except ValueError as exc:
            return {"ok": False, "reason": f"Command could not be parsed: {exc}", "tokens": []}

        tokens = [self._clean_token(token) for token in raw_tokens]
        if not tokens:
            return {"ok": False, "reason": "Empty command.", "tokens": []}
        return {"ok": True, "reason": None, "tokens": tokens}

    def _is_python_py_compile(self, lowered):
        python_names = {
            "python",
            "python.exe",
            "python3",
            "python3.exe",
            "py",
            "py.exe",
            Path(sys.executable).name.lower(),
        }
        return (
            len(lowered) >= 3
            and lowered[0] in python_names
            and lowered[1] == "-m"
            and lowered[2] == "py_compile"
        )

    def _clean_token(self, token):
        token = str(token or "").strip()
        if len(token) >= 2 and token[0] == token[-1] and token[0] in {'"', "'"}:
            return token[1:-1]
        return token

    def _is_inside_project(self, path):
        try:
            path.relative_to(self.project_root)
            return True
        except ValueError:
            return False

    def _failure(self, message, state):
        return {"ok": False, "message": message, "state": state}

    def _normalize_state_mode(self, state):
        if not isinstance(state, dict):
            return self._default_state()

        if state.get("approval_state") == "superseded_by_patch_approval":
            state["detected_mode"] = "engineering_task"
        elif state.get("final_result") == "no_shell_execution_for_engineering_task":
            state["detected_mode"] = "engineering_task"
        elif state.get("request_id") and not state.get("detected_mode"):
            state["detected_mode"] = "safe_command"
        else:
            state.setdefault("detected_mode", "waiting_for_input")
        return state

    def _default_state(self):
        return {
            "request_id": None,
            "detected_mode": "waiting_for_input",
            "requested_command": "",
            "approved_command": None,
            "interpreted_action": "No command requested.",
            "execution_plan": [],
            "risk_analysis": [],
            "risk_level": "none",
            "approval_required": True,
            "approval_state": "waiting_for_command",
            "execution_status": "IDLE",
            "safety_decision": {
                "allowed": False,
                "reason": "No command has been submitted.",
                "approval_required": True,
                "bounded_execution": True,
                "shell_execution": False,
                "destructive_execution": False,
                "deploy": False,
                "file_deletion": False,
            },
            "matched_whitelist": None,
            "actual_argv": [],
            "display_argv": [],
            "timeout_seconds": None,
            "cwd": str(self.project_root),
            "stdout": "",
            "stderr": "",
            "returncode": None,
            "final_result": "idle",
            "created_at": None,
            "updated_at": self._now(),
            "approved_at": None,
            "started_at": None,
            "finished_at": None,
        }

    def _read_history_locked(self):
        if not self.history_path.exists():
            return []
        try:
            history = json.loads(self.history_path.read_text(encoding="utf-8"))
            if isinstance(history, list):
                return history[-self.MAX_HISTORY :]
        except Exception:
            pass
        return []

    def _append_history_locked(self, entry):
        history = self._read_history_locked()
        history.append(entry)
        self._write_json(self.history_path, history[-self.MAX_HISTORY :])

    def _append_event_locked(self, event):
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
