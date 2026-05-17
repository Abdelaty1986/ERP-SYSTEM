import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"

HEALTH_REPORT = MEMORY_DIR / "cognition_health_report.json"
SILENCE_REPORT = MEMORY_DIR / "runtime_silence_detection.json"
COGNITION_TIMELINE = LOGS_DIR / "cognition_timeline.jsonl"
STABILITY_REPORT = MEMORY_DIR / "cognitive_stability_analysis.json"


class CognitiveStabilityAnalysis:
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

    def _count_timeline_events(self):
        if not COGNITION_TIMELINE.exists():
            return 0
        try:
            return len([
                line for line in COGNITION_TIMELINE.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ])
        except Exception:
            return 0

    def analyze(self):
        health = self._read_json(HEALTH_REPORT)
        silence = self._read_json(SILENCE_REPORT)
        timeline_count = self._count_timeline_events()

        health_state = health.get("health_state") if health else "unknown"
        health_score = health.get("health_score", 0) if health else 0
        silence_state = silence.get("silence_state") if silence else "unknown"
        silence_risk = silence.get("silence_risk") if silence else "unknown"

        stability_score = 100
        reasons = []

        if health_state != "stable":
            stability_score -= 25
            reasons.append(f"Health state is {health_state}.")

        if health_score < 80:
            stability_score -= 10
            reasons.append(f"Health score below stable threshold: {health_score}.")

        if silence_state != "active":
            stability_score -= 20
            reasons.append(f"Silence state is {silence_state}.")

        if silence_risk in {"medium", "high"}:
            stability_score -= 15
            reasons.append(f"Silence risk is {silence_risk}.")

        if timeline_count < 3:
            stability_score -= 10
            reasons.append(f"Timeline event count is low: {timeline_count}.")

        stability_score = max(0, min(100, stability_score))

        if stability_score >= 80:
            stability_state = "stable"
        elif stability_score >= 50:
            stability_state = "watch"
        else:
            stability_state = "unstable"

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "cognitive_stability_analysis",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "stability_state": stability_state,
            "stability_score": stability_score,
            "inputs": {
                "health_state": health_state,
                "health_score": health_score,
                "silence_state": silence_state,
                "silence_risk": silence_risk,
                "timeline_event_count": timeline_count,
            },
            "reasons": reasons,
            "recommendations": self._recommendations(stability_state),
        }

        STABILITY_REPORT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return report

    def _recommendations(self, stability_state):
        if stability_state == "stable":
            return ["Cognitive runtime is stable enough for the next bounded runtime layer."]

        if stability_state == "watch":
            return [
                "Continue bounded monitoring before unlocking any higher autonomy.",
                "Run additional wake cycles to enrich cognition timeline continuity."
            ]

        return [
            "Keep autonomous execution locked.",
            "Repair missing cognition continuity components before proceeding to long-running loops."
        ]


def analyze_stability():
    return CognitiveStabilityAnalysis().analyze()


if __name__ == "__main__":
    print(json.dumps(analyze_stability(), ensure_ascii=False, indent=2))
