import json

from jarvis.runtime.cognition_continuity import CognitionContinuity


if __name__ == "__main__":
    result = CognitionContinuity().aggregate()

    print(json.dumps({
        "runtime": "cognition_continuity_probe",
        "bounded": result["bounded"],
        "continuity_state": result["continuity_state"],
        "timeline_entries": result["timeline_entries"],
        "wake_cycle_count": result["wake_cycle_count"],
        "selected_agent": result["selected_agent"],
        "consensus_state": result["consensus_state"],
        "continuity_mode": result["continuity_mode"],
        "apply_allowed": result["apply_allowed"]
    }, ensure_ascii=False, indent=2))
