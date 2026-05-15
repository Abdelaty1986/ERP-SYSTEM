import json
from datetime import datetime, timezone
from pathlib import Path


MEMORY_DIR = Path("JARVIS_CORE/runtime_memory")
LOG_DIR = Path("JARVIS_CORE/runtime_logs")

COGNITION_STATE_PATH = MEMORY_DIR / "persistent_cognition_state.json"
TIMELINE_PATH = LOG_DIR / "cognition_timeline.jsonl"
SUMMARY_PATH = MEMORY_DIR / "cognition_timeline_summary.json"


class CognitionTimeline:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def load_state(self):
        if not COGNITION_STATE_PATH.exists():
            return {}

        return json.loads(
            COGNITION_STATE_PATH.read_text(encoding="utf-8")
        )

    def append_snapshot(self):
        state = self.load_state()

        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "cognition_timeline",
            "bounded": True,
            "cognition_state": state.get("cognition_state"),
            "selected_agent": state.get("selected_agent"),
            "consensus_state": state.get("consensus_state"),
            "latest_task": state.get("latest_task"),
            "persistence_mode": state.get("persistence_mode"),
            "execution_allowed": False,
            "apply_allowed": False
        }

        with TIMELINE_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")

        timeline_count = len([
            line for line in TIMELINE_PATH.read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip()
        ])

        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "cognition_timeline_summary",
            "bounded": True,
            "timeline_entries": timeline_count,
            "latest_cognition_state": snapshot["cognition_state"],
            "latest_selected_agent": snapshot["selected_agent"],
            "latest_consensus_state": snapshot["consensus_state"],
            "timeline_state": "recorded"
        }

        SUMMARY_PATH.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return summary


if __name__ == "__main__":
    result = CognitionTimeline().append_snapshot()

    print(json.dumps(result, ensure_ascii=False, indent=2))
