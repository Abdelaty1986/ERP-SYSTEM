import json

from jarvis.runtime.cognition_wake_cycle import CognitionWakeCycle


if __name__ == "__main__":
    result = CognitionWakeCycle().run_cycle()

    print(json.dumps({
        "runtime": "cognition_wake_cycle_probe",
        "bounded": result["bounded"],
        "wake_cycle_count": result["wake_cycle_count"],
        "wake_state": result["wake_state"],
        "selected_agent": result["selected_agent"],
        "consensus_state": result["consensus_state"],
        "cycle_mode": result["cycle_mode"],
        "apply_allowed": result["apply_allowed"]
    }, ensure_ascii=False, indent=2))
