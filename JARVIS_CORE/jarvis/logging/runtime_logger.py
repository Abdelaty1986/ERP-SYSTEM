from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime
import json
import uuid


@dataclass
class RuntimeLogEvent:
    event_id: str
    timestamp: str
    event_type: str
    project_id: str
    task: str
    status: str
    details: dict


class RuntimeLogger:
    def __init__(self, log_dir=None):
        self.log_dir = Path(log_dir or "JARVIS_CORE/runtime_logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.log_dir / "runtime_events.jsonl"

    def now(self):
        return datetime.now().isoformat(timespec="seconds")

    def log_event(self, event_type, project_id="ledgerx", task="", status="info", details=None):
        event = RuntimeLogEvent(
            event_id=str(uuid.uuid4()),
            timestamp=self.now(),
            event_type=event_type,
            project_id=project_id,
            task=task,
            status=status,
            details=details or {}
        )

        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")

        return event

    def read_recent(self, limit=20):
        if not self.events_path.exists():
            return []

        lines = self.events_path.read_text(encoding="utf-8").splitlines()
        recent = lines[-limit:]

        return [json.loads(line) for line in recent if line.strip()]
