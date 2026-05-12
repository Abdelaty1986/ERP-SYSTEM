from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any


LOG_DIR = Path("JARVIS_CORE/runtime_logs")

PATTERN_FILE = LOG_DIR / "runtime_pattern_awareness.json"
ADAPTIVE_FILE = LOG_DIR / "runtime_adaptive_observer.json"
FORECAST_FILE = LOG_DIR / "runtime_stability_forecast.json"
MEMORY_FILE = LOG_DIR / "runtime_observation_memory.json"

CORRELATION_FILE = LOG_DIR / "runtime_correlation_analysis.json"


class RuntimeCorrelationEngine:
    """
    Safe runtime cognitive correlation layer.

    Correlates:
    - wake cycles
    - silence trends
    - cognition persistence
    - adaptive risks
    - stability forecasting

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

    def save_result(self, payload: Dict[str, Any]) -> None:
        CORRELATION_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def analyze(self) -> Dict[str, Any]:
        pattern = self.load_json(PATTERN_FILE)
        adaptive = self.load_json(ADAPTIVE_FILE)
        forecast = self.load_json(FORECAST_FILE)
        memory = self.load_json(MEMORY_FILE)

        wake_count = pattern.get("wake_cycle_count", 0)
        silence_count = pattern.get("silence_detection_count", 0)

        cognition_count = len(memory.get("cognition_history", []))

        escalation_risk = adaptive.get("escalation_risk", "low")
        forecast_state = forecast.get("forecast_state", "unknown")

        correlation_strength = "weak"

        if wake_count >= 2 and cognition_count >= 2:
            correlation_strength = "moderate"

        if wake_count >= 3 and silence_count >= 3:
            correlation_strength = "strong"

        correlation_summary = {
            "timestamp": self.iso_now(),
            "wake_cycle_count": wake_count,
            "silence_detection_count": silence_count,
            "cognition_persistence": cognition_count,
            "escalation_risk": escalation_risk,
            "forecast_state": forecast_state,
            "correlation_strength": correlation_strength,
            "correlation_insights": [],
            "safe_mode": True,
            "bounded": True,
        }

        if wake_count >= 2 and cognition_count >= 2:
            correlation_summary["correlation_insights"].append(
                "Wake activity correlates with cognition persistence"
            )

        if silence_count >= 2:
            correlation_summary["correlation_insights"].append(
                "Runtime silence trend observed across cognition cycles"
            )

        if escalation_risk != "low":
            correlation_summary["correlation_insights"].append(
                "Adaptive escalation risk correlated with runtime instability"
            )

        if forecast_state != "stable":
            correlation_summary["correlation_insights"].append(
                "Forecast instability trend correlation detected"
            )

        self.save_result(correlation_summary)

        return correlation_summary


def main() -> None:
    result = RuntimeCorrelationEngine().analyze()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
