import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "learning_stability_monitor.json"
LOG_PATH = LOGS_DIR / "learning_stability_monitor.jsonl"

SOURCES = {
    "runtime_learning_summary": MEMORY_DIR / "runtime_learning_summary.json",
    "engineering_learning_memory": MEMORY_DIR / "engineering_learning_memory.json",
    "agent_performance_memory": MEMORY_DIR / "agent_performance_memory.json",
    "provider_scoring_memory": MEMORY_DIR / "provider_scoring_memory.json",
    "adaptive_routing_recommendations": MEMORY_DIR / "adaptive_routing_recommendations.json",
    "runtime_self_monitoring_hud": MEMORY_DIR / "runtime_self_monitoring_hud.json",
}


def load_json(path):
    if not path.exists():
        return {"exists": False, "data": None}
    try:
        return {"exists": True, "data": json.loads(path.read_text(encoding="utf-8"))}
    except Exception as exc:
        return {"exists": True, "data": None, "error": str(exc)}


class LearningStabilityMonitor:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        sources = {name: load_json(path) for name, path in SOURCES.items()}
        available = [name for name, item in sources.items() if item.get("exists") and item.get("data") is not None]
        missing = [name for name, item in sources.items() if not item.get("exists")]
        unreadable = [name for name, item in sources.items() if item.get("exists") and item.get("data") is None]

        summary = sources["runtime_learning_summary"].get("data") or {}
        hud = sources["runtime_self_monitoring_hud"].get("data") or {}
        cognitive = hud.get("cognitive_supervision", {})

        layer_states = summary.get("layer_states", {})
        review_items = summary.get("review_items", [])
        blocked = summary.get("blocked_capabilities", [])
        unsafe_layers = [name for name, state in layer_states.items() if state.get("execution_allowed") or state.get("apply_allowed")]
        stable_layers = [
            name for name, state in layer_states.items()
            if any(token in str(state.get("learning_state")) for token in ("stable", "ready", "strong"))
        ]

        cognitive_stable = (
            cognitive.get("health_state") == "stable"
            and cognitive.get("silence_state") == "active"
            and cognitive.get("stability_state") == "stable"
            and cognitive.get("reflection_state") == "clear"
            and cognitive.get("next_runtime_allowed") is True
        )
        safety_stability = "stable" if cognitive_stable and not unsafe_layers and not blocked and not unreadable else "unstable"
        learning_stability = "watch" if review_items else safety_stability

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "learning_stability_monitor",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "memory_mode": "safe_read_only_learning_stability_monitor",
            "phase": "phase_4_runtime_learning_system",
            "layer": "learning_stability_monitor",
            "available_source_count": len(available),
            "available_sources": available,
            "missing_sources": missing,
            "unreadable_sources": unreadable,
            "stability_inputs": {
                "layer_count": len(layer_states),
                "stable_layer_count": len(stable_layers),
                "review_item_count": len(review_items),
                "unsafe_layer_count": len(unsafe_layers),
                "health_state": cognitive.get("health_state"),
                "silence_state": cognitive.get("silence_state"),
                "stability_state": cognitive.get("stability_state"),
                "reflection_state": cognitive.get("reflection_state"),
            },
            "safety_stability": safety_stability,
            "learning_stability": learning_stability,
            "review_items": review_items,
            "unsafe_layers": unsafe_layers,
            "monitor_decision": {
                "next_runtime_allowed": safety_stability == "stable",
                "requires_human_review": bool(review_items),
                "allow_autonomous_execution": False,
                "allow_autonomous_apply": False,
            },
            "learning_assessment": {
                "learning_state": "learning_stability_watch" if learning_stability == "watch" else "stable_learning_runtime",
                "safe_to_display_in_hud": safety_stability == "stable",
                "may_execute_recommendations": False,
                "may_apply_changes": False,
            },
            "recommendation": "use_as_memory_input_for_safe_learning_hud_report",
            "result": "learning_stability_monitor_built",
        }
        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "learning_state": result["learning_assessment"]["learning_state"],
            "safety_stability": result["safety_stability"],
            "learning_stability": result["learning_stability"],
            "next_runtime_allowed": result["monitor_decision"]["next_runtime_allowed"],
            "execution_allowed": False,
            "apply_allowed": False,
            "human_approval_required": True,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(LearningStabilityMonitor().build(), ensure_ascii=False, indent=2))
