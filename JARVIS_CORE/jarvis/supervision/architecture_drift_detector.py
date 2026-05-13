import json
from pathlib import Path
from datetime import datetime

from jarvis.intelligence.erp_project_intelligence import build_erp_project_snapshot


class ArchitectureDriftDetector:
    def __init__(self):
        self.log_dir = Path("JARVIS_CORE/runtime_logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.history_path = self.log_dir / "architecture_drift_history.json"

    def _load_history(self):
        if not self.history_path.exists():
            return []
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_history(self, history):
        self.history_path.write_text(
            json.dumps(history[-20:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _compact_snapshot(self, snapshot):
        summary = snapshot.get("summary", {})
        relationships = snapshot.get("relationships", {})
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "route_count": summary.get("route_count", 0),
            "template_count": summary.get("template_count", 0),
            "module_count": summary.get("module_count", 0),
            "static_file_count": summary.get("static_file_count", 0),
            "route_categories": summary.get("route_categories", {}),
            "domain_map": relationships.get("domain_map", {}),
        }

    def _compare(self, previous, current):
        notes = []
        score = 0

        for key in ["route_count", "template_count", "module_count", "static_file_count"]:
            old = previous.get(key, 0)
            new = current.get(key, 0)
            diff = new - old

            if diff:
                notes.append(f"{key} changed by {diff}.")
                score += min(abs(diff) * 5, 30)

        old_domains = previous.get("domain_map", {})
        new_domains = current.get("domain_map", {})

        for domain, state in new_domains.items():
            old_state = old_domains.get(domain, {})
            template_diff = state.get("templates", 0) - old_state.get("templates", 0)
            module_diff = state.get("modules", 0) - old_state.get("modules", 0)

            if template_diff or module_diff:
                notes.append(
                    f"{domain} changed: templates {template_diff}, modules {module_diff}."
                )
                score += min((abs(template_diff) + abs(module_diff)) * 7, 35)

        drift_state = "stable"
        if score >= 60:
            drift_state = "high-drift"
        elif score >= 25:
            drift_state = "moderate-drift"
        elif score > 0:
            drift_state = "low-drift"

        return {
            "drift_score": score,
            "drift_state": drift_state,
            "drift_notes": notes[:20],
        }

    def build_drift_snapshot(self):
        erp_snapshot = build_erp_project_snapshot()
        current = self._compact_snapshot(erp_snapshot)
        history = self._load_history()

        previous = history[-1] if history else None

        if previous:
            drift = self._compare(previous, current)
        else:
            drift = {
                "drift_score": 0,
                "drift_state": "baseline",
                "drift_notes": ["Baseline architecture snapshot captured."],
            }

        history.append(current)
        self._save_history(history)

        return {
            "available": True,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "current": current,
            "history_count": len(history),
            "drift_score": drift["drift_score"],
            "drift_state": drift["drift_state"],
            "drift_notes": drift["drift_notes"],
            "safe_mode": True,
            "bounded": True,
            "autonomy": "observation_only",
        }


def build_architecture_drift_snapshot():
    return ArchitectureDriftDetector().build_drift_snapshot()
