import json

from jarvis.runtime.cognition_timeline import CognitionTimeline


if __name__ == "__main__":
    result = CognitionTimeline().append_snapshot()

    print(json.dumps({
        "runtime": "cognition_timeline_probe",
        "bounded": result["bounded"],
        "timeline_entries": result["timeline_entries"],
        "latest_cognition_state": result["latest_cognition_state"],
        "latest_selected_agent": result["latest_selected_agent"],
        "latest_consensus_state": result["latest_consensus_state"],
        "timeline_state": result["timeline_state"]
    }, ensure_ascii=False, indent=2))
