import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
CORRELATION_PATH = MEMORY_DIR / "outcome_correlation_engine.json"

SOURCES = {
    "learning_ingestion": MEMORY_DIR / "learning_ingestion_runtime.json",
    "failure_summary": MEMORY_DIR / "failure_summary.json",
    "learning_summary": MEMORY_DIR / "learning_summary.json",
    "model_trust": MEMORY_DIR / "model_trust_memory.json",
}


def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class OutcomeCorrelationEngine:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def analyze(self):
        data = {name: load_json(path) for name, path in SOURCES.items()}

        failures = data["failure_summary"].get("failures_recorded", 0)
        learning_events = data["learning_summary"].get("events_recorded", 0)
        top_failure_category = data["failure_summary"].get("top_failure_category")
        learning_state = data["learning_summary"].get("learning_state")
        trust_ranking = data["model_trust"].get("trust_ranking", [])

        risk_pressure = "low"
        if failures >= 50:
            risk_pressure = "high"
        elif failures >= 20:
            risk_pressure = "medium"

        learning_signal = "inactive"
        if learning_events >= 25 and learning_state == "active":
            learning_signal = "strong"
        elif learning_events > 0:
            learning_signal = "weak"

        correlation_strength = "weak"
        if risk_pressure == "medium" and learning_signal == "strong":
            correlation_strength = "moderate"
        elif risk_pressure == "high" and learning_signal == "strong":
            correlation_strength = "strong"

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "outcome_correlation_engine",
            "bounded": True,
            "dangerous_autonomous_apply": False,
            "correlation_mode": "safe_read_only_outcome_analysis",
            "signals": {
                "failures_recorded": failures,
                "learning_events": learning_events,
                "top_failure_category": top_failure_category,
                "learning_state": learning_state,
                "risk_pressure": risk_pressure,
                "learning_signal": learning_signal,
                "trusted_provider": trust_ranking[0]["provider"] if trust_ranking else None,
            },
            "correlations": [
                {
                    "name": "runtime_failure_to_learning_activity",
                    "strength": correlation_strength,
                    "interpretation": "Learning activity is responding to runtime validation pressure.",
                },
                {
                    "name": "provider_trust_to_routing_stability",
                    "strength": "moderate" if trust_ranking else "weak",
                    "interpretation": "Provider trust memory supports stable routing decisions.",
                },
            ],
            "recommendation": (
                "continue_bounded_learning"
                if correlation_strength in ("moderate", "strong")
                else "collect_more_runtime_signals"
            ),
            "result": "outcome_correlation_built",
        }

        CORRELATION_PATH.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return result


if __name__ == "__main__":
    result = OutcomeCorrelationEngine().analyze()
    print(json.dumps(result, ensure_ascii=False, indent=2))
