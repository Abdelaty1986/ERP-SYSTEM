import json
from datetime import datetime, timezone
from pathlib import Path


MEMORY_DIR = Path("JARVIS_CORE/runtime_memory")

AGENT_SOCIETY_STATE_PATH = MEMORY_DIR / "agent_society_aggregate_state.json"
COGNITION_STATE_PATH = MEMORY_DIR / "persistent_cognition_state.json"


class PersistentCognitionState:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def read_json(self, path: Path):
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def snapshot(self):
        agent_society = self.read_json(AGENT_SOCIETY_STATE_PATH)

        state = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "persistent_cognition_state",
            "bounded": True,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "cognition_state": "awake_snapshot",
            "source_runtime": agent_society.get("runtime"),
            "society_state": agent_society.get("society_state"),
            "agent_count": agent_society.get("agent_count", 0),
            "latest_task": agent_society.get("latest_task"),
            "selected_agent": agent_society.get("selected_agent"),
            "consensus_state": agent_society.get("consensus_state"),
            "execution_allowed": False,
            "apply_allowed": False,
            "approval_required": True,
            "persistence_mode": "snapshot_only"
        }

        COGNITION_STATE_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return state


if __name__ == "__main__":
    result = PersistentCognitionState().snapshot()
    print(json.dumps(result, ensure_ascii=False, indent=2))
