import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "agent_society_hud_section.json"
LOG_PATH = LOGS_DIR / "agent_society_hud_section.jsonl"


def load_json(name):
    path = MEMORY_DIR / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class AgentSocietyHudSection:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        registry = load_json("agent_society_registry.json")
        routing = load_json("agent_society_routing.json")
        delegation = load_json("agent_society_delegation.json")
        consensus = load_json("agent_society_consensus.json")
        event_summary = load_json("agent_society_event_summary.json")
        aggregate = load_json("agent_society_aggregate_state.json")

        agents = registry.get("agents", {})
        section = {
            "society_state": registry.get("society_state"),
            "agent_count": len(agents),
            "agents": {
                name: {
                    "role": data.get("role"),
                    "risk_level": data.get("risk_level"),
                    "can_apply": data.get("can_apply", False),
                }
                for name, data in agents.items()
            },
            "routing": {
                "selected_agent": routing.get("selected_agent"),
                "selected_role": routing.get("selected_role"),
                "routing_state": routing.get("routing_state"),
                "execution_allowed": routing.get("execution_allowed", False),
            },
            "delegation": {
                "workflow_state": delegation.get("workflow_state"),
                "workflow_steps": len(delegation.get("workflow", [])),
                "execution_allowed": delegation.get("execution_allowed", False),
            },
            "consensus": {
                "consensus_state": consensus.get("consensus_state"),
                "vote_count": len(consensus.get("votes", {})),
                "apply_allowed": consensus.get("apply_allowed", False),
            },
            "event_log": {
                "latest_event_type": event_summary.get("latest_event_type"),
                "event_log_path": event_summary.get("event_log_path"),
            },
            "aggregate": {
                "aggregate_state": aggregate.get("aggregate_state"),
                "latest_task": aggregate.get("latest_task"),
                "latest_event_type": aggregate.get("latest_event_type"),
            },
        }

        unsafe_agents = [name for name, data in agents.items() if data.get("can_apply")]
        section_state = "watch" if unsafe_agents else "stable"

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "agent_society_hud_section",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "hud_mode": "safe_read_only_agent_society_section",
            "phase": "phase_6_full_mobile_control_center",
            "layer": "agent_society_section",
            "section": section,
            "unsafe_agents": unsafe_agents,
            "section_state": section_state,
            "recommendation": "use_as_input_for_engineering_runtime_hud_section",
            "result": "agent_society_hud_section_built",
        }

        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "section_state": result["section_state"],
            "agent_count": result["section"]["agent_count"],
            "selected_agent": result["section"]["routing"]["selected_agent"],
            "execution_allowed": False,
            "apply_allowed": False,
            "human_approval_required": True,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(AgentSocietyHudSection().build(), ensure_ascii=False, indent=2))
