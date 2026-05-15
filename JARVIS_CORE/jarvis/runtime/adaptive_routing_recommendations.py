import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "adaptive_routing_recommendations.json"
LOG_PATH = LOGS_DIR / "adaptive_routing_recommendations.jsonl"

SOURCES = {
    "provider_scoring_memory": MEMORY_DIR / "provider_scoring_memory.json",
    "agent_performance_memory": MEMORY_DIR / "agent_performance_memory.json",
    "engineering_learning_memory": MEMORY_DIR / "engineering_learning_memory.json",
    "agent_society_routing": MEMORY_DIR / "agent_society_routing.json",
    "adaptive_model_routing_hud": MEMORY_DIR / "adaptive_model_routing_hud.json",
}


def load_json(path):
    if not path.exists():
        return {"exists": False, "data": None}
    try:
        return {"exists": True, "data": json.loads(path.read_text(encoding="utf-8"))}
    except Exception as exc:
        return {"exists": True, "data": None, "error": str(exc)}


class AdaptiveRoutingRecommendations:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        sources = {name: load_json(path) for name, path in SOURCES.items()}
        available = [name for name, item in sources.items() if item.get("exists") and item.get("data") is not None]
        missing = [name for name, item in sources.items() if not item.get("exists")]
        unreadable = [name for name, item in sources.items() if item.get("exists") and item.get("data") is None]

        provider_memory = sources["provider_scoring_memory"].get("data") or {}
        agent_memory = sources["agent_performance_memory"].get("data") or {}
        engineering = sources["engineering_learning_memory"].get("data") or {}
        current_routing = sources["agent_society_routing"].get("data") or {}
        prior_hud = sources["adaptive_model_routing_hud"].get("data") or {}

        review_flags = provider_memory.get("review_flags", [])
        ranked = provider_memory.get("ranked_providers", [])
        agent_recs = []
        for name, memory in (agent_memory.get("agent_performance") or {}).items():
            if memory.get("safe_for_planning_memory") and memory.get("performance_signal") != "registered_observation_only":
                agent_recs.append({
                    "agent": name,
                    "role": memory.get("role"),
                    "risk_level": memory.get("risk_level"),
                    "signal": memory.get("performance_signal"),
                })

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "adaptive_routing_recommendations",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "memory_mode": "safe_read_only_routing_recommendations",
            "phase": "phase_4_runtime_learning_system",
            "layer": "adaptive_routing_recommendations",
            "available_source_count": len(available),
            "available_sources": available,
            "missing_sources": missing,
            "unreadable_sources": unreadable,
            "recommendations": {
                "provider": {
                    "recommended_provider_for_review": ranked[0] if ranked else None,
                    "decision_state": "review_required_before_use" if review_flags else "recommendation_available",
                    "reason": "provider scoring found review flags" if review_flags else "provider scoring has no review flags",
                    "review_flags": review_flags,
                    "apply_to_runtime": False,
                },
                "agent": {
                    "current_selected_agent": current_routing.get("selected_agent"),
                    "recommended_planning_agents": agent_recs,
                    "decision_state": "planning_memory_only",
                    "apply_to_runtime": False,
                },
                "engineering": {
                    "learning_state": engineering.get("learning_assessment", {}).get("learning_state"),
                    "routing_constraint": "proposal_only_human_approval_required",
                    "apply_to_runtime": False,
                },
                "prior_hud": {
                    "recommended_provider": prior_hud.get("adaptive_routing_decision", {}).get("recommended_provider"),
                    "fallback_mode": prior_hud.get("adaptive_routing_decision", {}).get("fallback_mode"),
                },
            },
            "learning_assessment": {
                "learning_state": "routing_recommendations_need_review" if review_flags or unreadable else "stable_routing_recommendations",
                "safe_to_display_in_hud": bool(available) and not unreadable,
                "may_execute_recommendations": False,
                "may_apply_changes": False,
            },
            "recommendation": "use_as_memory_input_for_runtime_learning_summary",
            "result": "adaptive_routing_recommendations_built",
        }
        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def append_log(self, result):
        provider = result["recommendations"]["provider"]
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "learning_state": result["learning_assessment"]["learning_state"],
            "recommended_provider_for_review": provider["recommended_provider_for_review"],
            "provider_decision_state": provider["decision_state"],
            "execution_allowed": False,
            "apply_allowed": False,
            "human_approval_required": True,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(AdaptiveRoutingRecommendations().build(), ensure_ascii=False, indent=2))
