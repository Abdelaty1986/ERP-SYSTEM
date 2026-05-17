import json
from pathlib import Path

from jarvis.runtime.agent_society_event_log import AgentSocietyEventLog


if __name__ == "__main__":
    runtime = AgentSocietyEventLog()
    result = runtime.record_orchestration_event()

    log_path = Path("JARVIS_CORE/runtime_logs/agent_society_events.jsonl")
    event_count = 0

    if log_path.exists():
        event_count = len([
            line for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ])

    print(json.dumps({
        "runtime": "agent_society_event_log_probe",
        "bounded": result["bounded"],
        "summary_state": result["summary_state"],
        "latest_event_type": result["latest_event_type"],
        "latest_selected_agent": result["latest_selected_agent"],
        "latest_consensus_state": result["latest_consensus_state"],
        "event_count": event_count
    }, ensure_ascii=False, indent=2))
