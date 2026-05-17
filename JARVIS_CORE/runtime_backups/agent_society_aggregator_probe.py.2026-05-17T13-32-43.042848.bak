import json
from jarvis.runtime.agent_society_aggregator import AgentSocietyAggregator


if __name__ == "__main__":
    result = AgentSocietyAggregator().aggregate()

    print(json.dumps({
        "runtime": "agent_society_aggregator_probe",
        "bounded": result["bounded"],
        "aggregate_state": result["aggregate_state"],
        "agent_count": result["agent_count"],
        "selected_agent": result["selected_agent"],
        "workflow_steps": result["workflow_steps"],
        "consensus_state": result["consensus_state"],
        "apply_allowed": result["apply_allowed"],
        "sources": result["sources"]
    }, ensure_ascii=False, indent=2))
