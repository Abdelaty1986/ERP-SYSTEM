from datetime import datetime
import uuid


class RuntimeCommandAPI:
    ALLOWED_COMMANDS = {
        "system_review",
        "run_tests",
        "scan_errors",
        "improve",
        "report",
    }

    def __init__(self, logger=None):
        self.logger = logger

    def submit_command(self, command, payload=None, project_id="ledgerx"):
        payload = payload or {}
        command = str(command or "").strip().lower()

        command_id = str(uuid.uuid4())

        if command not in self.ALLOWED_COMMANDS:
            result = {
                "command_id": command_id,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "accepted": False,
                "status": "rejected",
                "reason": "command_not_allowed",
                "command": command,
                "payload": payload,
            }
        else:
            result = {
                "command_id": command_id,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "accepted": True,
                "status": "queued",
                "reason": "safe_command_queued_no_direct_apply",
                "command": command,
                "payload": payload,
            }

        if self.logger:
            self.logger.log_event(
                event_type="runtime_command_submitted",
                project_id=project_id,
                task=command,
                status=result["status"],
                details=result,
            )

        return result
