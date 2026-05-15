import json
from datetime import datetime, timezone
from pathlib import Path


MEMORY_DIR = Path("JARVIS_CORE/runtime_memory")

COGNITION_STATE_PATH = MEMORY_DIR / "persistent_cognition_state.json"
WAKE_CYCLE_PATH = MEMORY_DIR / "cognition_wake_cycle.json"


class CognitionWakeCycle:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def read_json(self, path: Path):
        if not path.exists():
            return {}

        return json.loads(path.read_text(encoding="utf-8"))

    def run_cycle(self):
        cognition = self.read_json(COGNITION_STATE_PATH)
        previous = self.read_json(WAKE_CYCLE_PATH)

        cycle_count = previous.get("wake_cycle_count", 0) + 1

        state = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "cognition_wake_cycle",
            "bounded": True,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "wake_cycle_count": cycle_count,
            "wake_state": "active",
            "cognition_state": cognition.get("cognition_state"),
            "selected_agent": cognition.get("selected_agent"),
            "consensus_state": cognition.get("consensus_state"),
            "latest_task": cognition.get("latest_task"),
            "execution_allowed": False,
            "apply_allowed": False,
            "approval_required": True,
            "cycle_mode": "bounded_awareness_cycle"
        }

        WAKE_CYCLE_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return state


if __name__ == "__main__":
    result = CognitionWakeCycle().run_cycle()

    print(json.dumps(result, ensure_ascii=False, indent=2))
