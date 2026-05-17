import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"

HEALTH_REPORT = MEMORY_DIR / "cognition_health_report.json"
SILENCE_REPORT = MEMORY_DIR / "runtime_silence_detection.json"
STABILITY_REPORT = MEMORY_DIR / "cognitive_stability_analysis.json"
LOOP_REPORT = MEMORY_DIR / "long_running_runtime_loop.json"

REFLECTION_REPORT = MEMORY_DIR / "cognitive_reflection_runtime.json"
REFLECTION_LOG = LOGS_DIR / "cognitive_reflection_runtime.jsonl"


class CognitiveReflectionRuntime:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def _read_json(self, path):
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def reflect(self):
        health = self._read_json(HEALTH_REPORT) or {}
        silence = self._read_json(SILENCE_REPORT) or {}
        stability = self._read_json(STABILITY_REPORT) or {}
        loop = self._read_json(LOOP_REPORT) or {}

        reflection_state = "clear"
        blockers = []

        if health.get("health_state") != "stable":
            reflection_state = "blocked"
            blockers.append("Cognition health is not stable.")

        if silence.get("silence_state") != "active":
            reflection_state = "blocked"
            blockers.append("Runtime silence state is not active.")

        if stability.get("stability_state") != "stable":
            reflection_state = "blocked"
            blockers.append("Cognitive stability is not stable.")

        if loop.get("loop_state") != "completed":
            reflection_state = "blocked"
            blockers.append("Long-running runtime loop has not completed.")

        reflection = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "cognitive_reflection_runtime",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "reflection_state": reflection_state,
            "summary": {
                "health_state": health.get("health_state", "unknown"),
                "health_score": health.get("health_score", 0),
                "silence_state": silence.get("silence_state", "unknown"),
                "silence_risk": silence.get("silence_risk", "unknown"),
                "stability_state": stability.get("stability_state", "unknown"),
                "stability_score": stability.get("stability_score", 0),
                "loop_state": loop.get("loop_state", "unknown"),
                "cycles_completed": loop.get("cycles_completed", 0),
            },
            "interpretation": self._interpret(reflection_state, blockers),
            "blockers": blockers,
            "next_runtime_allowed": reflection_state == "clear",
            "recommendations": self._recommendations(reflection_state),
        }

        REFLECTION_REPORT.write_text(
            json.dumps(reflection, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        with REFLECTION_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(reflection, ensure_ascii=False) + "\n")

        return reflection

    def _interpret(self, reflection_state, blockers):
        if reflection_state == "clear":
            return (
                "Persistent Cognitive Runtime is stable, active, and ready "
                "for bounded self-monitoring HUD integration."
            )

        return "Persistent Cognitive Runtime is not ready: " + "; ".join(blockers)

    def _recommendations(self, reflection_state):
        if reflection_state == "clear":
            return [
                "Proceed to Runtime Self-Monitoring HUD.",
                "Keep autonomous execution locked until explicit governance expansion."
            ]

        return [
            "Do not proceed to higher runtime layers until blockers are resolved.",
            "Re-run health, silence, stability, and loop checks after repair."
        ]


def reflect():
    return CognitiveReflectionRuntime().reflect()


if __name__ == "__main__":
    print(json.dumps(reflect(), ensure_ascii=False, indent=2))
