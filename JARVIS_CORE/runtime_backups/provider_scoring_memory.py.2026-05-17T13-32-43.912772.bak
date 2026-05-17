import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "provider_scoring_memory.json"
LOG_PATH = LOGS_DIR / "provider_scoring_memory.jsonl"

SOURCES = {
    "provider_model_validation": MEMORY_DIR / "provider_model_validation.json",
    "provider_trust_memory": MEMORY_DIR / "provider_trust_memory.json",
    "model_trust_memory": MEMORY_DIR / "model_trust_memory.json",
    "provider_strategy_memory": MEMORY_DIR / "provider_strategy_memory.json",
    "adaptive_model_routing_hud": MEMORY_DIR / "adaptive_model_routing_hud.json",
    "adaptive_learning_scoring": MEMORY_DIR / "adaptive_learning_scoring.json",
    "agent_performance_memory": MEMORY_DIR / "agent_performance_memory.json",
}


def load_json(path):
    if not path.exists():
        return {"exists": False, "data": None}
    try:
        return {"exists": True, "data": json.loads(path.read_text(encoding="utf-8"))}
    except Exception as exc:
        return {"exists": True, "data": None, "error": str(exc)}


class ProviderScoringMemory:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        sources = {name: load_json(path) for name, path in SOURCES.items()}
        available = [name for name, item in sources.items() if item.get("exists") and item.get("data") is not None]
        missing = [name for name, item in sources.items() if not item.get("exists")]
        unreadable = [name for name, item in sources.items() if item.get("exists") and item.get("data") is None]

        validation = sources["provider_model_validation"].get("data") or {}
        runtime_trust = sources["provider_trust_memory"].get("data") or {}
        model_trust = sources["model_trust_memory"].get("data") or {}
        agent_memory = sources["agent_performance_memory"].get("data") or {}
        routing_hud = sources["adaptive_model_routing_hud"].get("data") or {}

        provider_names = sorted(
            set((validation.get("providers") or {}).keys())
            | set((runtime_trust.get("providers") or {}).keys())
            | set((model_trust.get("providers") or {}).keys())
        )

        provider_scores = {}
        review_flags = []
        for provider in provider_names:
            static_entry = (validation.get("providers") or {}).get(provider, {})
            runtime_entry = (runtime_trust.get("providers") or {}).get(provider, {})
            model_entry = (model_trust.get("providers") or {}).get(provider, {})
            validation_score = float(static_entry.get("confidence_score", 0.0) or 0.0)
            runtime_score = float(runtime_entry.get("trust_score", 0.0) or 0.0)
            model_score = float(model_entry.get("trust_score", 0.0) or 0.0)
            combined = round((validation_score * 0.35) + (runtime_score * 0.4) + (model_score * 0.25), 3)
            review_reason = None
            if static_entry.get("ready") and not runtime_entry:
                review_reason = "static_validation_ready_but_runtime_trust_missing"
            elif static_entry.get("ready") and runtime_entry.get("last_state") == "missing_credentials":
                review_reason = "static_validation_ready_but_runtime_credentials_missing"
            elif model_entry.get("trust_state") == "trusted" and runtime_entry.get("last_state") == "missing_credentials":
                review_reason = "model_trust_high_but_runtime_credentials_missing"
            if review_reason:
                review_flags.append({"provider": provider, "reason": review_reason})
            provider_scores[provider] = {
                "validation_state": static_entry.get("validation_state"),
                "runtime_state": runtime_entry.get("last_state"),
                "model_trust_state": model_entry.get("trust_state"),
                "configured_model": static_entry.get("model") or model_entry.get("model"),
                "validation_confidence": validation_score,
                "runtime_trust_score": runtime_score,
                "model_trust_score": model_score,
                "combined_observation_score": combined,
                "ready_in_static_validation": bool(static_entry.get("ready")),
                "review_required": bool(review_reason),
                "recommendation_scope": "routing_memory_only",
            }

        ranked = sorted(provider_scores, key=lambda name: provider_scores[name]["combined_observation_score"], reverse=True)
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "provider_scoring_memory",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "memory_mode": "safe_read_only_provider_scoring",
            "phase": "phase_4_runtime_learning_system",
            "layer": "provider_scoring_memory",
            "available_source_count": len(available),
            "available_sources": available,
            "missing_sources": missing,
            "unreadable_sources": unreadable,
            "provider_count": len(provider_names),
            "provider_scores": provider_scores,
            "ranked_providers": ranked,
            "recommended_provider_for_review": ranked[0] if ranked else None,
            "prior_routing_recommendation": routing_hud.get("adaptive_routing_decision", {}).get("recommended_provider"),
            "agent_learning_state": agent_memory.get("learning_assessment", {}).get("learning_state"),
            "review_flags": review_flags,
            "learning_assessment": {
                "learning_state": "provider_scores_need_review" if review_flags or unreadable else "stable_provider_scoring_memory",
                "safe_to_inform_routing_recommendations": bool(provider_names),
                "may_execute_recommendations": False,
                "may_apply_changes": False,
            },
            "recommendation": "use_as_memory_input_for_adaptive_routing_recommendations",
            "result": "provider_scoring_memory_built",
        }
        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "learning_state": result["learning_assessment"]["learning_state"],
            "provider_count": result["provider_count"],
            "recommended_provider_for_review": result["recommended_provider_for_review"],
            "review_flag_count": len(result["review_flags"]),
            "execution_allowed": False,
            "apply_allowed": False,
            "human_approval_required": True,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(ProviderScoringMemory().build(), ensure_ascii=False, indent=2))
