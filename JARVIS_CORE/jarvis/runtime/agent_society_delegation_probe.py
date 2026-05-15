import json
from jarvis.runtime.agent_society_delegation import AgentSocietyDelegation


if __name__ == "__main__":
    runtime = AgentSocietyDelegation()

    result = runtime.delegate(
        "implement safe dashboard patch"
    )

    print(json.dumps({
        "runtime": "agent_society_delegation_probe",
        "bounded": result["bounded"],
        "workflow_state": result["workflow_state"],
        "workflow_steps": len(result["workflow"]),
        "agents": [
            step["agent"]
            for step in result["workflow"]
        ]
    }, ensure_ascii=False, indent=2))
