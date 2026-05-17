import json
from jarvis.runtime.agent_society_orchestrator import AgentSocietyOrchestrator


if __name__ == "__main__":
    runtime = AgentSocietyOrchestrator()

    result = runtime.execute(
        "implement safe runtime dashboard patch"
    )

    print(json.dumps({
        "runtime": "agent_society_orchestrator_probe",
        "bounded": result["bounded"],
        "selected_agent": result["selected_agent"],
        "workflow_state": result["workflow_state"],
        "consensus_state": result["consensus_state"],
        "workflow_steps": result["workflow_steps"],
        "orchestration_state": result["orchestration_state"],
        "execution_allowed": result["execution_allowed"],
        "apply_allowed": result["apply_allowed"]
    }, ensure_ascii=False, indent=2))
