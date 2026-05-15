import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"

COGNITION_STATE = MEMORY_DIR / "persistent_cognition_state.json"
COGNITION_TIMELINE = LOGS_DIR / "cognition_timeline.jsonl"
CONTINUITY_STATE = MEMORY_DIR / "cognition_continuity_state.json"
HEALTH_REPORT = MEMORY_DIR / "cognition_health_report.json"


class CognitionHealthMonitor:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def _load_json(self, path):
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

    def build_report(self):
        cognition_state = self._load_json(COGNITION_STATE)
        continuity_state = self._load_json(CONTINUITY_STATE)
        timeline_count = self._count_timeline_events()

        missing = []
        if cognition_state is None:
            missing.append("persistent_cognition_state")
        if continuity_state is None:
            missing.append("cognition_continuity_state")
        if timeline_count == 0:
            missing.append("cognition_timeline")

        health_score = 100
        health_score -= len(missing) * 20
        if timeline_count < 2:
            health_score -= 10

        health_score = max(0, min(100, health_score))

        if health_score >= 80:
            health_state = "stable"
        elif health_score >= 50:
            health_state = "degraded"
        else:
            health_state = "critical"

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "cognition_health_monitor",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "health_state": health_state,
            "health_score": health_score,
            "checks": {
                "persistent_cognition_state_exists": cognition_state is not None,
                "cognition_continuity_state_exists": continuity_state is not None,
                "cognition_timeline_event_count": timeline_count,
                "missing_components": missing,
            },
            "recommendations": self._recommendations(health_state, missing, timeline_count),
        }

        HEALTH_REPORT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return report

    def _recommendations(self, health_state, missing, timeline_count):
        recommendations = []

        if missing:
            recommendations.append("Restore or regenerate missing cognition runtime components.")

        if timeline_count < 2:
            recommendations.append("Run cognition wake cycle again to enrich timeline continuity.")

        if health_state == "stable":
            recommendations.append("Cognition runtime appears stable and ready for next monitoring layer.")

        return recommendations


def build_report():
    return CognitionHealthMonitor().build_report()


if __name__ == "__main__":
    print(json.dumps(build_report(), ensure_ascii=False, indent=2))
