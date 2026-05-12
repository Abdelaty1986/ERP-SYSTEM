import json
import uuid
from pathlib import Path
from datetime import datetime


class RuntimeTimeline:

    def __init__(self, log_dir="JARVIS_CORE/runtime_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.timeline_file = self.log_dir / "runtime_timeline.jsonl"

    def _now(self):
        return datetime.utcnow().isoformat() + "Z"

    def add_event(
        self,
        session_id,
        stage,
        agent_id="system",
        status="info",
        message=None,
        payload=None
    ):
        event = {
            "event_id": str(uuid.uuid4()),
            "session_id": session_id,
            "stage": stage,
            "agent_id": agent_id,
            "status": status,
            "message": message,
            "payload": payload or {},
            "timestamp": self._now(),
        }

        with self.timeline_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

        return event

    def list_events(self, session_id=None, limit=50):
        if not self.timeline_file.exists():
            return []

        lines = self.timeline_file.read_text(encoding="utf-8").splitlines()

        events = []
        for line in lines:
            try:
                event = json.loads(line)
                if session_id is None or event.get("session_id") == session_id:
                    events.append(event)
            except Exception:
                pass

        return events[-limit:]
