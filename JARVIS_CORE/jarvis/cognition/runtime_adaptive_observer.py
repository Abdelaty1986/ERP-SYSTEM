from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any


LOG_DIR = Path("JARVIS_CORE/runtime_logs")

MEMORY_FILE = LOG_DIR / "runtime_observation_memory.json"
PATTERN_FILE = LOG_DIR / "runtime_pattern_awareness.json"
ADAPTIVE_FILE = LOG_DIR / "runtime_adaptive_observer.json"


class RuntimeAdaptiveObserver:
    """
    Safe adaptive runtime observer.

    Detects:
    - escalation trends
    - repeated instability
    - cognition growth
    - degradation patterns

    Does NOT:
    - execute actions
    - apply fixes
    - perform autonomous behavior
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
        ADAPTIVE_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def analyze(self) -> Dict[str, Any]:
        memory = self.load_json(MEMORY_FILE)
        patterns = self.load_json(PATTERN_FILE)

        wake_history = memory.get("wake_history", [])
        cognition_history = memory.get("cognition_history", [])

        wake_count = len(wake_history)
        cognition_count = len(cognition_history)

        instability = patterns.get("unstable_runtime_pattern", False)

        escalation_risk = "low"

        if wake_count >= 3 or cognition_count >= 3:
            escalation_risk = "medium"

        if wake_count >= 5 or cognition_count >= 5:
            escalation_risk = "high"

        degradation_detected = instability and escalation_risk != "low"

        adaptive_summary = {
            "timestamp": self.iso_now(),
            "wake_history_size": wake_count,
            "cognition_history_size": cognition_count,
            "instability_detected": instability,
            "escalation_risk": escalation_risk,
            "degradation_detected": degradation_detected,
            "adaptive_observations": [],
            "safe_mode": True,
            "bounded": True,
        }

        if wake_count >= 3:
            adaptive_summary["adaptive_observations"].append(
                "Wake cycle frequency increasing"
            )

        if cognition_count >= 3:
            adaptive_summary["adaptive_observations"].append(
                "Cognition persistence increasing"
            )

        if degradation_detected:
            adaptive_summary["adaptive_observations"].append(
                "Potential runtime degradation trend detected"
            )

        self.save_result(adaptive_summary)

        return adaptive_summary


def main() -> None:
    result = RuntimeAdaptiveObserver().analyze()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
