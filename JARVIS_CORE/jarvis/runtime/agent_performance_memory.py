import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"

OUTPUT_PATH = MEMORY_DIR / "agent_performance_memory.json"
LOG_PATH = LOGS_DIR / "agent_performance_memory.jsonl"

SOURCES = {
    "agent_society_registry": MEMORY_DIR / "agent_society_registry.json",
    "agent_society_routing": MEMORY_DIR / "agent_society_routing.json",
    "agent_society_delegation": MEMORY_DIR / "agent_society_delegation.json",
    "agent_society_consensus": MEMORY_DIR / "agent_society_consensus.json",
    "agent_society_orchestrator": MEMORY_DIR / "agent_society_orchestrator.json",
    "agent_society_event_summary": MEMORY_DIR / "agent_society_event_summary.json",
    "agent_society_aggregate_state": MEMORY_DIR / "agent_society_aggregate_state.json",
    "engineering_learning_memory": MEMORY_DIR / "engineering_learning_memory.json",
}


def load_json(path):
    if not path.exists():
        return {"exists": False, "data": None}

    try:
        return {
            "exists": True,
            "data": json.loads(path.read_text(encoding="utf-8")),
        }
    except Exception as exc:
        return {
            "exists": True,
            "data": None,
            "error": str(exc),
        }


class AgentPerformanceMemory:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        sources = {
            name: load_json(path)
            for name, path in SOURCES.items()
        }

        available_sources = [
            name
            for name, payload in sources.items()
            if payload.get("exists") and payload.get("data") is not None
        ]
        missing_sources = [
            name
            for name, payload in sources.items()
            if not payload.get("exists")
        ]
        unreadable_sources = [
            name
            for name, payload in sources.items()
            if payload.get("exists") and payload.get("data") is None
        ]

        registry = sources["agent_society_registry"].get("data") or {}
        routing = sources["agent_society_routing"].get("data") or {}
        delegation = sources["agent_society_delegation"].get("data") or {}
        consensus = sources["agent_society_consensus"].get("data") or {}
        orchestrator = sources["agent_society_orchestrator"].get("data") or {}
        aggregate = sources["agent_society_aggregate_state"].get("data") or {}
        engineering = sources["engineering_learning_memory"].get("data") or {}

        agents = registry.get("agents", {})
        workflow = delegation.get("workflow", [])
        votes = consensus.get("votes", {})
        selected_agent = routing.get("selected_agent") or orchestrator.get("selected_agent")

        performance = {}
        for agent_name, definition in agents.items():
            workflow_steps = [
                step for step in workflow
                if step.get("agent") == agent_name
            ]
            vote = votes.get(agent_name, {})
            selected = agent_name == selected_agent
            can_apply = bool(definition.get("can_apply"))

            performance[agent_name] = {
                "role": definition.get("role"),
                "risk_level": definition.get("risk_level"),
                "selected_for_latest_task": selected,
                "workflow_participation_count": len(workflow_steps),
                "latest_vote": vote.get("vote"),
                "latest_vote_reason": vote.get("reason"),
                "can_apply": can_apply,
                "safe_for_planning_memory": not can_apply,
                "performance_signal": self.performance_signal(
                    selected=selected,
                    workflow_steps=workflow_steps,
                    vote=vote,
                    can_apply=can_apply,
                ),
            }

        locked_controls = {
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
        }

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "agent_performance_memory",
            **locked_controls,
            "memory_mode": "safe_read_only_agent_performance_learning",
            "phase": "phase_4_runtime_learning_system",
            "layer": "agent_performance_memory",
            "available_source_count": len(available_sources),
            "available_sources": available_sources,
            "missing_sources": missing_sources,
            "unreadable_sources": unreadable_sources,
            "agent_count": len(agents),
            "latest_task": orchestrator.get("task") or routing.get("task"),
            "selected_agent": selected_agent,
            "workflow_state": delegation.get("workflow_state"),
            "consensus_state": consensus.get("consensus_state"),
            "aggregate_state": aggregate.get("aggregate_state"),
            "engineering_learning_state": (
                engineering.get("learning_assessment", {}).get("learning_state")
            ),
            "agent_performance": performance,
            "learning_assessment": {
                "learning_state": (
                    "stable_agent_performance_memory"
                    if agents and available_sources and not unreadable_sources
                    else "agent_performance_needs_review"
                ),
                "safe_to_inform_routing_recommendations": bool(agents)
                and not unreadable_sources,
                "may_execute_recommendations": False,
                "may_apply_changes": False,
            },
            "recommendation": "use_as_memory_input_for_provider_scoring_memory",
            "result": "agent_performance_memory_built",
        }

        OUTPUT_PATH.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.append_log(result)

        return result

    def performance_signal(self, selected, workflow_steps, vote, can_apply):
        if can_apply:
            return "blocked_from_apply_capability"
        if vote.get("vote") == "approve":
            return "positive_planning_signal"
        if selected:
            return "selected_for_bounded_planning"
        if workflow_steps:
            return "participated_in_bounded_workflow"
        return "registered_observation_only"

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "learning_state": result["learning_assessment"]["learning_state"],
            "agent_count": result["agent_count"],
            "selected_agent": result["selected_agent"],
            "execution_allowed": False,
            "apply_allowed": False,
            "human_approval_required": True,
        }

        with LOG_PATH.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    output = AgentPerformanceMemory().build()
    print(json.dumps(output, ensure_ascii=False, indent=2))
