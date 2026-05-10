from pathlib import Path
from datetime import datetime
import json


class AuditTrail:
    """
    Append-only audit trail for Jarvis controlled execution.
    Stores runtime events as JSON Lines.
    """

    def __init__(self, root="."):
        self.root = Path(root)
        self.audit_dir = (
            self.root
            / "JARVIS_CORE/jarvis/execution/sandbox/audit"
        )
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.audit_file = self.audit_dir / "audit_trail.jsonl"

    def record(self, event_type, payload):
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "payload": payload,
        }

        with self.audit_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

        return {
            "status": "recorded",
            "event_type": event_type,
            "audit_file": str(self.audit_file),
        }
