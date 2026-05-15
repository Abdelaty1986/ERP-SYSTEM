import json
from datetime import datetime, timezone
from pathlib import Path


MEMORY_DIR = Path("JARVIS_CORE/runtime_memory")

COGNITION_STATE_PATH = MEMORY_DIR / "persistent_cognition_state.json"
TIMELINE_SUMMARY_PATH = MEMORY_DIR / "cognition_timeline_summary.json"
WAKE_CYCLE_PATH = MEMORY_DIR / "cognition_wake_cycle.json"
CONTINUITY_PATH = MEMORY_DIR / "cognition_continuity.json"


class CognitionContinuity:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def read_json(self, path: Path):
        if not path.exists():
            return {}

        return json.loads(path.read_text(encoding="utf-8"))

    def aggregate(self):
        cognition = self.read_json(COGNITION_STATE_PATH)
        timeline = self.read_json(TIMELINE_SUMMARY_PATH)
        wake_cycle = self.read_json(WAKE_CYCLE_PATH)

        state = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "cognition_continuity",
            "bounded": True,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "continuity_state": "persistent",
            "cognition_state": cognition.get("cognition_state"),
            "selected_agent": cognition.get("selected_agent"),
            "consensus_state": cognition.get("consensus_state"),
            "timeline_entries": timeline.get("timeline_entries", 0),
            "wake_cycle_count": wake_cycle.get("wake_cycle_count", 0),
            "latest_task": cognition.get("latest_task"),
            "execution_allowed": False,
            "apply_allowed": False,
            "approval_required": True,
            "continuity_mode": "bounded_cognitive_persistence"
        }

        CONTINUITY_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return state


if __name__ == "__main__":
    result = CognitionContinuity().aggregate()

    print(json.dumps(result, ensure_ascii=False, indent=2))
