import json
from pathlib import Path
from datetime import datetime, timezone


TIMELINE_FILE = Path("JARVIS_CORE/runtime_memory/execution_timeline.json")


class ExecutionTimelineRuntime:
    def append_event(self, event):
        timeline = []

        if TIMELINE_FILE.exists():
            try:
                timeline = json.loads(TIMELINE_FILE.read_text(encoding="utf-8"))
            except Exception:
                timeline = []

        event["timestamp"] = datetime.now(timezone.utc).isoformat()
        timeline.append(event)

        TIMELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
        TIMELINE_FILE.write_text(
            json.dumps(timeline, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return event

    def read(self):
        if not TIMELINE_FILE.exists():
            return []

        return json.loads(TIMELINE_FILE.read_text(encoding="utf-8"))
