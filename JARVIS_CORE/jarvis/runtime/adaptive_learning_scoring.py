import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
SCORING_PATH = MEMORY_DIR / "adaptive_learning_scoring.json"

CORRELATION_PATH = MEMORY_DIR / "outcome_correlation_engine.json"
LEARNING_SUMMARY_PATH = MEMORY_DIR / "learning_summary.json"
FAILURE_SUMMARY_PATH = MEMORY_DIR / "failure_summary.json"


def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class AdaptiveLearningScoring:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def score(self):
        correlation = load_json(CORRELATION_PATH)
        learning_summary = load_json(LEARNING_SUMMARY_PATH)
        failure_summary = load_json(FAILURE_SUMMARY_PATH)

        learning_events = learning_summary.get("events_recorded", 0)
        failures = failure_summary.get("failures_recorded", 0)
        recommendation = correlation.get("recommendation", "collect_more_runtime_signals")

        base_score = min(learning_events / 40, 1.0)
        pressure_factor = min(failures / 50, 1.0)
        recommendation_factor = 1.0 if recommendation == "continue_bounded_learning" else 0.5

        adaptive_score = round(
            (base_score * 0.45) +
            (pressure_factor * 0.25) +
            (recommendation_factor * 0.30),
            2,
        )

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "adaptive_learning_scoring",
            "bounded": True,
            "dangerous_autonomous_apply": False,
            "scoring_mode": "safe_read_only_adaptive_learning_score",
            "inputs": {
                "learning_events": learning_events,
                "failures_recorded": failures,
                "correlation_recommendation": recommendation,
            },
            "score_components": {
                "base_score": round(base_score, 2),
                "pressure_factor": round(pressure_factor, 2),
                "recommendation_factor": recommendation_factor,
            },
            "adaptive_learning_score": adaptive_score,
            "learning_state": (
                "strong_adaptive_signal"
                if adaptive_score >= 0.75 else
                "moderate_adaptive_signal"
                if adaptive_score >= 0.45 else
                "weak_adaptive_signal"
            ),
            "recommended_next_action": (
                "continue_memory_compression"
                if adaptive_score >= 0.45 else
                "collect_more_signals_before_compression"
            ),
            "result": "adaptive_learning_score_built",
        }

        SCORING_PATH.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return result


if __name__ == "__main__":
    result = AdaptiveLearningScoring().score()
    print(json.dumps(result, ensure_ascii=False, indent=2))
