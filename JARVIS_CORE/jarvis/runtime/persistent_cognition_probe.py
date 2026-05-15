import json
from jarvis.runtime.persistent_cognition_state import PersistentCognitionState


if __name__ == "__main__":
    result = PersistentCognitionState().snapshot()

    print(json.dumps({
        "runtime": "persistent_cognition_probe",
        "bounded": result["bounded"],
        "cognition_state": result["cognition_state"],
        "source_runtime": result["source_runtime"],
        "agent_count": result["agent_count"],
        "selected_agent": result["selected_agent"],
        "consensus_state": result["consensus_state"],
        "apply_allowed": result["apply_allowed"],
        "persistence_mode": result["persistence_mode"]
    }, ensure_ascii=False, indent=2))
