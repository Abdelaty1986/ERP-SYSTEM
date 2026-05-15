import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "safe_learning_hud_report.json"
LOG_PATH = LOGS_DIR / "safe_learning_hud_report.jsonl"

SOURCES = {
    "engineering_learning_memory": MEMORY_DIR / "engineering_learning_memory.json",
    "agent_performance_memory": MEMORY_DIR / "agent_performance_memory.json",
    "provider_scoring_memory": MEMORY_DIR / "provider_scoring_memory.json",
    "adaptive_routing_recommendations": MEMORY_DIR / "adaptive_routing_recommendations.json",
    "runtime_learning_summary": MEMORY_DIR / "runtime_learning_summary.json",
    "learning_stability_monitor": MEMORY_DIR / "learning_stability_monitor.json",
}


def load_json(path):
    if not path.exists():
        return {"exists": False, "data": None}
    try:
        return {"exists": True, "data": json.loads(path.read_text(encoding="utf-8"))}
    except Exception as exc:
        return {"exists": True, "data": None, "error": str(exc)}


class SafeLearningHudReport:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        sources = {name: load_json(path) for name, path in SOURCES.items()}
        available = [name for name, item in sources.items() if item.get("exists") and item.get("data") is not None]
        missing = [name for name, item in sources.items() if not item.get("exists")]
        unreadable = [name for name, item in sources.items() if item.get("exists") and item.get("data") is None]

        engineering = sources["engineering_learning_memory"].get("data") or {}
        agents = sources["agent_performance_memory"].get("data") or {}
        providers = sources["provider_scoring_memory"].get("data") or {}
        routing = sources["adaptive_routing_recommendations"].get("data") or {}
        summary = sources["runtime_learning_summary"].get("data") or {}
        stability = sources["learning_stability_monitor"].get("data") or {}

        warnings = [
            {"type": "provider_review", "message": item.get("reason"), "subject": item.get("provider")}
            for item in summary.get("review_items", [])
        ]
        if unreadable:
            warnings.append({"type": "source_read_error", "message": "One or more learning sources could not be read.", "subject": unreadable})

        provider_rec = routing.get("recommendations", {}).get("provider", {})
        agent_rec = routing.get("recommendations", {}).get("agent", {})
        hud = {
            "title": "Runtime Learning System",
            "phase": "Phase 4",
            "status": stability.get("learning_stability", "unknown"),
            "safety_stability": stability.get("safety_stability"),
            "next_runtime_allowed": stability.get("monitor_decision", {}).get("next_runtime_allowed", False),
            "requires_human_review": stability.get("monitor_decision", {}).get("requires_human_review", True),
            "sections": {
                "engineering_learning": {
                    "state": engineering.get("learning_assessment", {}).get("learning_state"),
                    "active_strategy": engineering.get("engineering_signals", {}).get("active_strategy"),
                    "active_goal": engineering.get("engineering_signals", {}).get("active_goal"),
                },
                "agent_performance": {
                    "state": agents.get("learning_assessment", {}).get("learning_state"),
                    "agent_count": agents.get("agent_count"),
                    "selected_agent": agents.get("selected_agent"),
                },
                "provider_scoring": {
                    "state": providers.get("learning_assessment", {}).get("learning_state"),
                    "provider_count": providers.get("provider_count"),
                    "recommended_provider_for_review": providers.get("recommended_provider_for_review"),
                },
                "routing_recommendations": {
                    "state": routing.get("learning_assessment", {}).get("learning_state"),
                    "provider_decision_state": provider_rec.get("decision_state"),
                    "agent_decision_state": agent_rec.get("decision_state"),
                },
            },
            "warnings": warnings,
            "locks": {
                "execution_allowed": False,
                "apply_allowed": False,
                "autonomous_apply": False,
                "dangerous_autonomous_apply": False,
                "human_approval_required": True,
            },
        }

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "safe_learning_hud_report",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "memory_mode": "safe_read_only_learning_hud",
            "phase": "phase_4_runtime_learning_system",
            "layer": "safe_learning_hud_report",
            "available_source_count": len(available),
            "available_sources": available,
            "missing_sources": missing,
            "unreadable_sources": unreadable,
            "hud": hud,
            "learning_assessment": {
                "learning_state": "safe_learning_hud_review_visible" if warnings else "safe_learning_hud_stable",
                "safe_to_display_in_hud": not unreadable,
                "may_execute_recommendations": False,
                "may_apply_changes": False,
            },
            "recommendation": "phase_4_complete_continue_to_external_toolchain_runtime",
            "result": "safe_learning_hud_report_built",
        }
        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "learning_state": result["learning_assessment"]["learning_state"],
            "hud_status": result["hud"]["status"],
            "warning_count": len(result["hud"]["warnings"]),
            "next_runtime_allowed": result["hud"]["next_runtime_allowed"],
            "execution_allowed": False,
            "apply_allowed": False,
            "human_approval_required": True,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(SafeLearningHudReport().build(), ensure_ascii=False, indent=2))
