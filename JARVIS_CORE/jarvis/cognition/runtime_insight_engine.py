import json
from pathlib import Path
from datetime import datetime


class RuntimeInsightEngine:
    def __init__(self):
        self.correlation_path = Path("JARVIS_CORE/runtime_logs/runtime_correlation_analysis.json")

    def _load_json(self, path):
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def build_insights(self):
        data = self._load_json(self.correlation_path)

        strength = data.get("correlation_strength", "unknown")
        forecast = data.get("forecast_state", "unknown")
        risk = data.get("escalation_risk", "unknown")
        wake_count = data.get("wake_cycle_count", 0)
        silence_count = data.get("silence_detection_count", 0)
        cognition = data.get("cognition_persistence", 0)

        explanations = []

        if strength in ("moderate", "strong"):
            explanations.append("Runtime behavior shows meaningful correlation between wake activity and cognition persistence.")
        elif strength == "weak":
            explanations.append("Runtime correlation is currently weak and needs more observation cycles.")
        else:
            explanations.append("Runtime correlation state is still unknown.")

        if forecast == "stable":
            explanations.append("Current stability forecast indicates the runtime is operating within safe bounded limits.")
        elif forecast == "unstable":
            explanations.append("Runtime stability forecast indicates possible degradation and should be monitored.")
        else:
            explanations.append("Runtime stability forecast is not yet conclusive.")

        if risk == "low":
            explanations.append("Escalation risk is low based on current silence and cognition signals.")
        elif risk in ("medium", "high"):
            explanations.append("Escalation risk increased and may require closer supervision.")
        else:
            explanations.append("Escalation risk is not yet classified.")

        if silence_count and cognition:
            explanations.append("Silence detection and cognition persistence are both present, which supports adaptive runtime awareness.")

        return {
            "available": bool(data),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "summary": {
                "correlation_strength": strength,
                "forecast_state": forecast,
                "escalation_risk": risk,
                "wake_cycle_count": wake_count,
                "silence_detection_count": silence_count,
                "cognition_persistence": cognition,
            },
            "insight_count": len(explanations),
            "insights": explanations,
            "safe_mode": True,
            "bounded": True,
        }


def build_runtime_insight_snapshot():
    return RuntimeInsightEngine().build_insights()
