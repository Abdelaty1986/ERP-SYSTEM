import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"

COGNITION_STATE = MEMORY_DIR / "persistent_cognition_state.json"
COGNITION_TIMELINE = LOGS_DIR / "cognition_timeline.jsonl"
CONTINUITY_STATE = MEMORY_DIR / "cognition_continuity_state.json"
REPAIR_REPORT = MEMORY_DIR / "cognition_continuity_repair.json"


class CognitionContinuityRepair:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def _read_json(self, path):
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _read_timeline_events(self):
        if not COGNITION_TIMELINE.exists():
            return []

        events = []
        for line in COGNITION_TIMELINE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                continue
        return events

    def repair(self):
        cognition_state = self._read_json(COGNITION_STATE)
        events = self._read_timeline_events()
        latest_event = events[-1] if events else None

        continuity = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "cognition_continuity_repair",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "continuity_state": "repaired",
            "continuity_source": {
                "persistent_cognition_state_exists": cognition_state is not None,
                "timeline_event_count": len(events),
                "latest_timeline_event": latest_event,
            },
            "current_awareness": {
                "cognition_state": (
                    cognition_state.get("cognition_state")
                    if isinstance(cognition_state, dict)
                    else "unknown"
                ),
                "selected_agent": (
                    cognition_state.get("selected_agent")
                    if isinstance(cognition_state, dict)
                    else None
                ),
                "consensus_state": (
                    cognition_state.get("consensus_state")
                    if isinstance(cognition_state, dict)
                    else None
                ),
                "latest_task": (
                    cognition_state.get("latest_task")
                    if isinstance(cognition_state, dict)
                    else None
                ),
            },
            "safety": {
                "human_approval_required": True,
                "autonomous_unlock_allowed": False,
                "long_running_loop_allowed": False,
                "reason": "Continuity repaired, but additional wake cycles are required before long-running loops."
            },
        }

        CONTINUITY_STATE.write_text(
            json.dumps(continuity, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "cognition_continuity_repair",
            "bounded": True,
            "repair_state": "completed",
            "created_or_updated": str(CONTINUITY_STATE),
            "timeline_event_count": len(events),
            "long_running_loop_allowed": False,
            "recommendations": [
                "Run cognition wake cycle at least two more times.",
                "Re-run health, silence, and stability analysis after timeline enrichment."
            ]
        }

        REPAIR_REPORT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return report


def repair_continuity():
    return CognitionContinuityRepair().repair()


if __name__ == "__main__":
    print(json.dumps(repair_continuity(), ensure_ascii=False, indent=2))
