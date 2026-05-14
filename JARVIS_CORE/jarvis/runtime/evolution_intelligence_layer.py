import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
EVOLUTION_PATH = MEMORY_DIR / "evolution_intelligence_layer.json"

COMPRESSION_PATH = MEMORY_DIR / "memory_compression_runtime.json"
SCORING_PATH = MEMORY_DIR / "adaptive_learning_scoring.json"


def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class EvolutionIntelligenceLayer:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def evolve(self):
        compression = load_json(COMPRESSION_PATH)
        scoring = load_json(SCORING_PATH)

        memory = compression.get("compressed_memory", {})
        adaptive_score = scoring.get("adaptive_learning_score", 0)

        if adaptive_score >= 0.75:
            evolution_state = "ready_for_guided_evolution"
        elif adaptive_score >= 0.45:
            evolution_state = "observe_and_continue_learning"
        else:
            evolution_state = "insufficient_signal"

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "evolution_intelligence_layer",
            "bounded": True,
            "dangerous_autonomous_apply": False,
            "evolution_mode": "safe_guided_runtime_evolution",
            "compressed_memory_used": True if memory else False,
            "adaptive_learning_score": adaptive_score,
            "evolution_state": evolution_state,
            "evolution_guidance": {
                "preferred_strategy": memory.get("top_strategy"),
                "active_goal": memory.get("top_goal"),
                "risk_state": memory.get("risk_state"),
                "recommended_path": (
                    "continue_bounded_architecture_refinement"
                    if evolution_state == "ready_for_guided_evolution"
                    else "continue_signal_collection"
                ),
            },
            "guardrails": {
                "bounded_execution": True,
                "rollback_required": True,
                "human_review_required": True,
                "autonomous_apply_allowed": False,
            },
            "result": "evolution_intelligence_built",
        }

        EVOLUTION_PATH.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return result


if __name__ == "__main__":
    result = EvolutionIntelligenceLayer().evolve()
    print(json.dumps(result, ensure_ascii=False, indent=2))
