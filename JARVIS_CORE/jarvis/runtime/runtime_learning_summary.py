import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "runtime_learning_summary.json"
LOG_PATH = LOGS_DIR / "runtime_learning_summary.jsonl"

SOURCES = {
    "engineering_learning_memory": MEMORY_DIR / "engineering_learning_memory.json",
    "agent_performance_memory": MEMORY_DIR / "agent_performance_memory.json",
    "provider_scoring_memory": MEMORY_DIR / "provider_scoring_memory.json",
    "adaptive_routing_recommendations": MEMORY_DIR / "adaptive_routing_recommendations.json",
    "learning_ingestion_runtime": MEMORY_DIR / "learning_ingestion_runtime.json",
    "adaptive_learning_scoring": MEMORY_DIR / "adaptive_learning_scoring.json",
}


def load_json(path):
    if not path.exists():
        return {"exists": False, "data": None}
    try:
        return {"exists": True, "data": json.loads(path.read_text(encoding="utf-8"))}
    except Exception as exc:
        return {"exists": True, "data": None, "error": str(exc)}


class RuntimeLearningSummary:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        sources = {name: load_json(path) for name, path in SOURCES.items()}
        available = [name for name, item in sources.items() if item.get("exists") and item.get("data") is not None]
        missing = [name for name, item in sources.items() if not item.get("exists")]
        unreadable = [name for name, item in sources.items() if item.get("exists") and item.get("data") is None]

        layer_states = {}
        blocked_capabilities = []
        review_items = []
        for name, item in sources.items():
            data = item.get("data") or {}
            state = data.get("learning_assessment", {}).get("learning_state") or data.get("learning_state") or data.get("result")
            layer_states[name] = {
                "available": item.get("exists") and data != {},
                "learning_state": state,
                "execution_allowed": bool(data.get("execution_allowed")),
                "apply_allowed": bool(data.get("apply_allowed")),
                "human_approval_required": data.get("human_approval_required", True),
            }
            if data.get("execution_allowed") or data.get("apply_allowed"):
                blocked_capabilities.append(name)

        provider_memory = sources["provider_scoring_memory"].get("data") or {}
        routing_memory = sources["adaptive_routing_recommendations"].get("data") or {}
        review_items.extend(provider_memory.get("review_flags", []))
        review_items.extend(routing_memory.get("recommendations", {}).get("provider", {}).get("review_flags", []))
        unique_review_items = []
        seen = set()
        for item in review_items:
            key = (item.get("provider"), item.get("reason"))
            if key not in seen:
                seen.add(key)
                unique_review_items.append(item)

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "runtime_learning_summary",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "memory_mode": "safe_read_only_runtime_learning_summary",
            "phase": "phase_4_runtime_learning_system",
            "layer": "runtime_learning_summary",
            "available_source_count": len(available),
            "available_sources": available,
            "missing_sources": missing,
            "unreadable_sources": unreadable,
            "layer_states": layer_states,
            "review_items": unique_review_items,
            "blocked_capabilities": blocked_capabilities,
            "learning_summary": {
                "engineering_learning": layer_states.get("engineering_learning_memory", {}).get("learning_state"),
                "agent_learning": layer_states.get("agent_performance_memory", {}).get("learning_state"),
                "provider_learning": layer_states.get("provider_scoring_memory", {}).get("learning_state"),
                "routing_learning": layer_states.get("adaptive_routing_recommendations", {}).get("learning_state"),
                "review_required": bool(unique_review_items),
            },
            "learning_assessment": {
                "learning_state": "runtime_learning_review_required" if unique_review_items or unreadable else "stable_runtime_learning_summary",
                "safe_to_display_in_hud": bool(available) and not unreadable,
                "may_execute_recommendations": False,
                "may_apply_changes": False,
            },
            "recommendation": "use_as_memory_input_for_learning_stability_monitor",
            "result": "runtime_learning_summary_built",
        }
        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "learning_state": result["learning_assessment"]["learning_state"],
            "available_source_count": result["available_source_count"],
            "review_item_count": len(result["review_items"]),
            "execution_allowed": False,
            "apply_allowed": False,
            "human_approval_required": True,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(RuntimeLearningSummary().build(), ensure_ascii=False, indent=2))
