import json
from datetime import datetime, timezone
from pathlib import Path


LOG_DIR = Path("JARVIS_CORE/runtime_logs")
MEMORY_DIR = Path("JARVIS_CORE/runtime_memory")
ORCHESTRATOR_PATH = MEMORY_DIR / "agent_society_orchestrator.json"
EVENT_LOG_PATH = LOG_DIR / "agent_society_events.jsonl"
SUMMARY_PATH = MEMORY_DIR / "agent_society_event_summary.json"


class AgentSocietyEventLog:
    def __init__(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def load_orchestration(self):
        if not ORCHESTRATOR_PATH.exists():
            return {}
        return json.loads(ORCHESTRATOR_PATH.read_text(encoding="utf-8"))

    def append_event(self, event_type: str, message: str, payload=None):
        payload = payload or {}

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "agent_society_event_log",
            "bounded": True,
            "event_type": event_type,
            "message": message,
            "payload": payload
        }

        with EVENT_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

        return event

    def record_orchestration_event(self):
        orchestration = self.load_orchestration()

        event = self.append_event(
            event_type="orchestration_recorded",
            message="Agent society orchestration state recorded.",
            payload={
                "task": orchestration.get("task"),
                "selected_agent": orchestration.get("selected_agent"),
                "workflow_steps": orchestration.get("workflow_steps"),
                "consensus_state": orchestration.get("consensus_state"),
                "apply_allowed": orchestration.get("apply_allowed", False)
            }
        )

        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "agent_society_event_summary",
            "bounded": True,
            "latest_event_type": event["event_type"],
            "latest_selected_agent": orchestration.get("selected_agent"),
            "latest_consensus_state": orchestration.get("consensus_state"),
            "event_log_path": str(EVENT_LOG_PATH),
            "summary_state": "updated"
        }

        SUMMARY_PATH.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return summary


if __name__ == "__main__":
    result = AgentSocietyEventLog().record_orchestration_event()
    print(json.dumps(result, ensure_ascii=False, indent=2))
