from pathlib import Path
from datetime import datetime
import json

class FailureLearningEngine:
    def __init__(self, root="."):
        self.root = Path(root)
        self.memory_dir = self.root / "JARVIS_CORE" / "runtime_memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.failure_file = self.memory_dir / "failure_memory.jsonl"
        self.summary_file = self.memory_dir / "failure_summary.json"

    def record_failure(
        self,
        category,
        cause,
        severity="medium",
        affected_component="unknown",
        recovery="manual_review"
    ):
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "bounded": True,
            "mode": "failure_learning",
            "autonomous_apply": False,
            "category": category,
            "cause": cause,
            "severity": severity,
            "affected_component": affected_component,
            "recovery": recovery,
        }

        with self.failure_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

        summary = self._build_summary()

        self.summary_file.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return {
            "bounded": True,
            "mode": "failure_learning",
            "autonomous_apply": False,
            "failure_event": event,
            "summary": summary,
            "notes": [
                "Failure learning records repeated engineering risks.",
                "This layer is observational only.",
                "No autonomous recovery execution is performed."
            ]
        }

    def _build_summary(self):
        events = self._read_events()

        categories = {}
        severities = {}
        components = {}

        for event in events:
            categories[event["category"]] = categories.get(event["category"], 0) + 1
            severities[event["severity"]] = severities.get(event["severity"], 0) + 1
            components[event["affected_component"]] = components.get(event["affected_component"], 0) + 1

        return {
            "failures_recorded": len(events),
            "top_failure_category": self._top(categories),
            "top_affected_component": self._top(components),
            "risk_state": self._risk_state(severities),
            "severity_distribution": severities,
            "failure_categories": categories,
        }

    def _risk_state(self, severities):
        high = severities.get("high", 0)
        critical = severities.get("critical", 0)

        if critical >= 3:
            return "critical_watch"

        if high >= 3:
            return "elevated_risk"

        return "stable"

    def _top(self, mapping):
        if not mapping:
            return None
        return max(mapping, key=mapping.get)

    def _read_events(self):
        if not self.failure_file.exists():
            return []

        rows = []

        for line in self.failure_file.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:
                continue

        return rows
