import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"

COGNITION_TIMELINE = LOGS_DIR / "cognition_timeline.jsonl"
HEALTH_REPORT = MEMORY_DIR / "cognition_health_report.json"
SILENCE_REPORT = MEMORY_DIR / "runtime_silence_detection.json"


class RuntimeSilenceDetection:
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

    def _read_timeline_events(self):
        if not COGNITION_TIMELINE.exists():
            return []

        events = []
        for line in COGNITION_TIMELINE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                continue
        return events

    def detect(self):
        events = self._read_timeline_events()
        health_report = self._read_json(HEALTH_REPORT)

        timeline_event_count = len(events)
        latest_event = events[-1] if events else None

        silence_state = "active"
        silence_risk = "low"
        reasons = []

        if timeline_event_count == 0:
            silence_state = "silent"
            silence_risk = "high"
            reasons.append("No cognition timeline events found.")
        elif timeline_event_count == 1:
            silence_state = "low_activity"
            silence_risk = "medium"
            reasons.append("Only one cognition timeline event found.")

        if health_report and health_report.get("health_state") != "stable":
            if silence_risk == "low":
                silence_risk = "medium"
            reasons.append("Cognition health report is not stable.")

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "runtime_silence_detection",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "silence_state": silence_state,
            "silence_risk": silence_risk,
            "timeline_event_count": timeline_event_count,
            "latest_event": latest_event,
            "health_state": health_report.get("health_state") if health_report else "unknown",
            "reasons": reasons,
            "recommendations": self._recommendations(silence_state, silence_risk),
        }

        SILENCE_REPORT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return report

    def _recommendations(self, silence_state, silence_risk):
        recommendations = []

        if silence_state in {"silent", "low_activity"}:
            recommendations.append("Run cognition wake cycle to increase runtime activity continuity.")

        if silence_risk in {"medium", "high"}:
            recommendations.append("Do not unlock autonomous execution until cognition activity stabilizes.")

        if not recommendations:
            recommendations.append("Runtime activity appears sufficient for the next monitoring layer.")

        return recommendations


def detect_silence():
    return RuntimeSilenceDetection().detect()


if __name__ == "__main__":
    print(json.dumps(detect_silence(), ensure_ascii=False, indent=2))
