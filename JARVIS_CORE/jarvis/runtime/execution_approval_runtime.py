import json
from pathlib import Path
from datetime import datetime, timezone


APPROVAL_FILE = Path("JARVIS_CORE/runtime_memory/execution_approval_state.json")


class ExecutionApprovalRuntime:
    def set_waiting(self, command):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "approval_state": "waiting_approval",
            "command": command,
            "real_execution_allowed": False,
            "bounded": True,
            "dangerous_execution": False,
        }

        APPROVAL_FILE.parent.mkdir(parents=True, exist_ok=True)
        APPROVAL_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return payload

    def approve(self):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "approval_state": "approved",
            "real_execution_allowed": True,
            "bounded": True,
            "dangerous_execution": False,
        }

        APPROVAL_FILE.parent.mkdir(parents=True, exist_ok=True)
        APPROVAL_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return payload

    def reject(self):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "approval_state": "rejected",
            "real_execution_allowed": False,
            "bounded": True,
            "dangerous_execution": False,
        }

        APPROVAL_FILE.parent.mkdir(parents=True, exist_ok=True)
        APPROVAL_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return payload

    def read(self):
        if not APPROVAL_FILE.exists():
            return {
                "approval_state": "none",
                "real_execution_allowed": False,
                "bounded": True,
            }

        return json.loads(APPROVAL_FILE.read_text(encoding="utf-8"))
