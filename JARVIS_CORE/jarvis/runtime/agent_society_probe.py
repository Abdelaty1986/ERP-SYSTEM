import json
from jarvis.runtime.agent_society_registry import AgentSocietyRegistry

if __name__ == "__main__":
    state = AgentSocietyRegistry().write_state()
    print(json.dumps({
        "runtime": "agent_society_probe",
        "bounded": state.get("bounded"),
        "society_state": state.get("society_state"),
        "agent_count": len(state.get("agents", {})),
        "human_approval_required": state.get("policy", {}).get("human_approval_required"),
        "auto_git_commit": state.get("policy", {}).get("auto_git_commit"),
        "auto_git_push": state.get("policy", {}).get("auto_git_push")
    }, ensure_ascii=False, indent=2))
