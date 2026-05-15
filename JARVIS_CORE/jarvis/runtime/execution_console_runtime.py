import json
from pathlib import Path
from datetime import datetime, timezone


STATE_FILE = Path("JARVIS_CORE/runtime_memory/execution_console_state.json")


class ExecutionConsoleRuntime:
    def write_state(self, state):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "execution_console_runtime",
            "bounded": True,
            "state": state,
        }

        STATE_FILE.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return payload

    def read_state(self):
        if not STATE_FILE.exists():
            return self.write_state(
                {
                    "current_task": None,
                    "execution_status": "IDLE",
                    "approval_state": "WAITING_FOR_COMMAND",
                }
            )

        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
