import json
from pathlib import Path
from datetime import datetime, timezone


MEMORY = Path("JARVIS_CORE/runtime_memory/runtime_command_history.json")


class ExecutionHistoryRuntime:
    def read(self):
        if not MEMORY.exists():
            return []

        try:
            return json.loads(MEMORY.read_text(encoding="utf-8"))
        except Exception:
            return []

    def append(self, payload):
        MEMORY.parent.mkdir(parents=True, exist_ok=True)

        history = self.read()
        payload["logged_at"] = datetime.now(timezone.utc).isoformat()

        history.append(payload)

        MEMORY.write_text(
            json.dumps(history, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return payload
