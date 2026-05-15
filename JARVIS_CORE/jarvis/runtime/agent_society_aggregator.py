import json
from datetime import datetime, timezone
from pathlib import Path


MEMORY_DIR = Path("JARVIS_CORE/runtime_memory")

REGISTRY_PATH = MEMORY_DIR / "agent_society_registry.json"
ROUTING_PATH = MEMORY_DIR / "agent_society_routing.json"
DELEGATION_PATH = MEMORY_DIR / "agent_society_delegation.json"
CONSENSUS_PATH = MEMORY_DIR / "agent_society_consensus.json"
ORCHESTRATOR_PATH = MEMORY_DIR / "agent_society_orchestrator.json"
EVENT_SUMMARY_PATH = MEMORY_DIR / "agent_society_event_summary.json"
AGGREGATE_PATH = MEMORY_DIR / "agent_society_aggregate_state.json"


class AgentSocietyAggregator:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def read_json(self, path: Path):
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def aggregate(self):
        registry = self.read_json(REGISTRY_PATH)
        routing = self.read_json(ROUTING_PATH)
        delegation = self.read_json(DELEGATION_PATH)
        consensus = self.read_json(CONSENSUS_PATH)
        orchestrator = self.read_json(ORCHESTRATOR_PATH)
        event_summary = self.read_json(EVENT_SUMMARY_PATH)

        state = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "agent_society_aggregator",
            "bounded": True,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "society_state": registry.get("society_state", "unknown"),
            "agent_count": len(registry.get("agents", {})),
            "latest_task": orchestrator.get("task"),
            "selected_agent": orchestrator.get("selected_agent"),
            "workflow_state": delegation.get("workflow_state"),
            "workflow_steps": orchestrator.get("workflow_steps", 0),
            "consensus_state": consensus.get("consensus_state"),
            "latest_event_type": event_summary.get("latest_event_type"),
            "execution_allowed": False,
            "apply_allowed": False,
            "approval_required": True,
            "aggregate_state": "ready",
            "sources": {
                "registry": REGISTRY_PATH.exists(),
                "routing": ROUTING_PATH.exists(),
                "delegation": DELEGATION_PATH.exists(),
                "consensus": CONSENSUS_PATH.exists(),
                "orchestrator": ORCHESTRATOR_PATH.exists(),
                "event_summary": EVENT_SUMMARY_PATH.exists()
            }
        }

        AGGREGATE_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return state


if __name__ == "__main__":
    result = AgentSocietyAggregator().aggregate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
