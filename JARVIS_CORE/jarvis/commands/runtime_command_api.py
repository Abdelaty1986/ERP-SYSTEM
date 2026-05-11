from datetime import datetime
from pathlib import Path
import uuid
import json


class RuntimeCommandAPI:
    ALLOWED_COMMANDS = {
        "system_review",
        "run_tests",
        "scan_errors",
        "improve",
        "report",
    }

    def __init__(self, logger=None, queue_path=None):
        self.logger = logger
        self.queue_path = Path(queue_path or "JARVIS_CORE/runtime_logs/runtime_command_queue.jsonl")
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)

    def persist_command(self, result):
        with self.queue_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
        return result

    def read_queue(self, limit=20):
        if not self.queue_path.exists():
            return []

        lines = self.queue_path.read_text(encoding="utf-8").splitlines()
        recent = lines[-limit:]
        return [json.loads(line) for line in recent if line.strip()]

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

        self.persist_command(result)

        if self.logger:
            self.logger.log_event(
                event_type="runtime_command_submitted",
                project_id=project_id,
                task=command,
                status=result["status"],
                details=result,
            )

        return result
