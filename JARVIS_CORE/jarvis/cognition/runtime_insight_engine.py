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

        def add_insight(category, severity, priority, message):
            explanations.append({
                "category": category,
                "severity": severity,
                "priority": priority,
                "message": message,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            })

        if strength in ("moderate", "strong"):
            add_insight(
                "correlation",
                "info",
                2,
                "Runtime behavior shows meaningful correlation between wake activity and cognition persistence.",
            )
        elif strength == "weak":
            add_insight(
                "correlation",
                "watch",
                3,
                "Runtime correlation is currently weak and needs more observation cycles.",
            )
        else:
            add_insight(
                "correlation",
                "unknown",
                4,
                "Runtime correlation state is still unknown.",
            )

        if forecast == "stable":
            add_insight(
                "stability",
                "safe",
                1,
                "Current stability forecast indicates the runtime is operating within safe bounded limits.",
            )
        elif forecast == "unstable":
            add_insight(
                "stability",
                "warning",
                5,
                "Runtime stability forecast indicates possible degradation and should be monitored.",
            )
        else:
            add_insight(
                "stability",
                "unknown",
                4,
                "Runtime stability forecast is not yet conclusive.",
            )

        if risk == "low":
            add_insight(
                "escalation",
                "safe",
                1,
                "Escalation risk is low based on current silence and cognition signals.",
            )
        elif risk in ("medium", "high"):
            add_insight(
                "escalation",
                "warning",
                5,
                "Escalation risk increased and may require closer supervision.",
            )
        else:
            add_insight(
                "escalation",
                "unknown",
                4,
                "Escalation risk is not yet classified.",
            )

        if silence_count and cognition:
            add_insight(
                "adaptive-awareness",
                "info",
                2,
                "Silence detection and cognition persistence are both present, which supports adaptive runtime awareness.",
            )

        explanations = sorted(explanations, key=lambda item: item.get("priority", 99), reverse=True)

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
