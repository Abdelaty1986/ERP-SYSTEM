from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List


LOG_DIR = Path("JARVIS_CORE/runtime_logs")
MEMORY_FILE = LOG_DIR / "runtime_observation_memory.json"
PATTERN_FILE = LOG_DIR / "runtime_pattern_awareness.json"


class RuntimePatternAwareness:
    """
    Safe runtime pattern awareness layer.

    Detects:
    - repeated wake cycles
    - repeated silence
    - cognition repetition
    - unstable runtime patterns

    Does NOT:
    - execute actions
    - apply repairs
    - make autonomous decisions
    """

    def iso_now(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def load_memory(self) -> Dict[str, Any]:
        if not MEMORY_FILE.exists():
            return {}

        try:
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_patterns(self, payload: Dict[str, Any]) -> None:
        PATTERN_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def detect_patterns(self) -> Dict[str, Any]:
        memory = self.load_memory()

        wake_history = memory.get("wake_history", [])
        silence_history = memory.get("silence_history", [])
        cognition_history = memory.get("cognition_history", [])

        wake_count = len(wake_history)
        silence_count = sum(
            1 for item in silence_history
            if item.get("silence_detected") is True
        )

        repeated_reasoning = {}
        for item in cognition_history:
            reasoning = item.get("reasoning", "unknown")
            repeated_reasoning[reasoning] = repeated_reasoning.get(reasoning, 0) + 1

        dominant_reasoning = None
        dominant_reasoning_count = 0

        if repeated_reasoning:
            dominant_reasoning = max(
                repeated_reasoning,
                key=repeated_reasoning.get
            )
            dominant_reasoning_count = repeated_reasoning[dominant_reasoning]

        unstable_runtime = (
            wake_count >= 3
            or silence_count >= 3
        )

        pattern_summary = {
            "timestamp": self.iso_now(),
            "wake_cycle_count": wake_count,
            "silence_detection_count": silence_count,
            "dominant_reasoning": dominant_reasoning,
            "dominant_reasoning_count": dominant_reasoning_count,
            "unstable_runtime_pattern": unstable_runtime,
            "observations": [],
            "safe_mode": True,
            "bounded": True,
        }

        if wake_count >= 3:
            pattern_summary["observations"].append(
                "Repeated wake cycles detected"
            )

        if silence_count >= 3:
            pattern_summary["observations"].append(
                "Persistent runtime silence detected"
            )

        if dominant_reasoning_count >= 2:
            pattern_summary["observations"].append(
                "Repeated cognition reasoning pattern observed"
            )

        self.save_patterns(pattern_summary)

        return pattern_summary


def main() -> None:
    result = RuntimePatternAwareness().detect_patterns()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
