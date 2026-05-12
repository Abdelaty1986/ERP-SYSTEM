from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any


LOG_DIR = Path("JARVIS_CORE/runtime_logs")

PATTERN_FILE = LOG_DIR / "runtime_pattern_awareness.json"
ADAPTIVE_FILE = LOG_DIR / "runtime_adaptive_observer.json"
FORECAST_FILE = LOG_DIR / "runtime_stability_forecast.json"


class RuntimeStabilityForecaster:
    """
    Safe runtime stability forecasting layer.

    Forecasts:
    - instability likelihood
    - escalation probability
    - degradation trend probability

    Does NOT:
    - execute actions
    - apply repairs
    - trigger autonomy
    """

    def iso_now(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def load_json(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_forecast(self, payload: Dict[str, Any]) -> None:
        FORECAST_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def forecast(self) -> Dict[str, Any]:
        pattern = self.load_json(PATTERN_FILE)
        adaptive = self.load_json(ADAPTIVE_FILE)

        wake_count = pattern.get("wake_cycle_count", 0)
        silence_count = pattern.get("silence_detection_count", 0)

        escalation_risk = adaptive.get("escalation_risk", "low")
        degradation_detected = adaptive.get("degradation_detected", False)

        stability_score = 100

        stability_score -= wake_count * 5
        stability_score -= silence_count * 5

        if escalation_risk == "medium":
            stability_score -= 15

        if escalation_risk == "high":
            stability_score -= 30

        if degradation_detected:
            stability_score -= 20

        stability_score = max(stability_score, 0)

        forecast_state = "stable"

        if stability_score <= 70:
            forecast_state = "monitor"

        if stability_score <= 45:
            forecast_state = "unstable"

        if stability_score <= 25:
            forecast_state = "critical"

        forecast_summary = {
            "timestamp": self.iso_now(),
            "forecast_state": forecast_state,
            "stability_score": stability_score,
            "wake_cycle_count": wake_count,
            "silence_detection_count": silence_count,
            "escalation_risk": escalation_risk,
            "degradation_detected": degradation_detected,
            "forecast_observations": [],
            "safe_mode": True,
            "bounded": True,
        }

        if wake_count >= 3:
            forecast_summary["forecast_observations"].append(
                "Wake cycle growth may reduce runtime stability"
            )

        if silence_count >= 3:
            forecast_summary["forecast_observations"].append(
                "Persistent silence may increase instability risk"
            )

        if escalation_risk != "low":
            forecast_summary["forecast_observations"].append(
                "Escalation risk trend detected"
            )

        self.save_forecast(forecast_summary)

        return forecast_summary


def main() -> None:
    result = RuntimeStabilityForecaster().forecast()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
