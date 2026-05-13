import json
from pathlib import Path
from datetime import datetime


class StructuralTrendForecaster:
    def __init__(self):
        self.history_path = Path("JARVIS_CORE/runtime_logs/architecture_drift_history.json")

    def _load_history(self):
        if not self.history_path.exists():
            return []
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _delta(self, history, key):
        if len(history) < 2:
            return 0
        return history[-1].get(key, 0) - history[0].get(key, 0)

    def _domain_trends(self, history):
        if len(history) < 2:
            return []

        first = history[0].get("domain_map", {})
        last = history[-1].get("domain_map", {})
        trends = []

        for domain, state in last.items():
            old = first.get(domain, {})
            template_delta = state.get("templates", 0) - old.get("templates", 0)
            module_delta = state.get("modules", 0) - old.get("modules", 0)

            if template_delta or module_delta:
                trends.append({
                    "domain": domain,
                    "template_delta": template_delta,
                    "module_delta": module_delta,
                    "direction": "growing" if template_delta + module_delta > 0 else "shrinking",
                })

        return trends

    def build_forecast(self):
        history = self._load_history()

        route_delta = self._delta(history, "route_count")
        template_delta = self._delta(history, "template_count")
        module_delta = self._delta(history, "module_count")
        static_delta = self._delta(history, "static_file_count")

        domain_trends = self._domain_trends(history)

        score = 0
        score += min(abs(route_delta) * 4, 30)
        score += min(abs(template_delta) * 5, 30)
        score += min(abs(module_delta) * 8, 30)
        score += min(abs(static_delta) * 3, 15)
        score += min(len(domain_trends) * 6, 30)

        forecast_state = "stable"
        if score >= 60:
            forecast_state = "accelerating-change"
        elif score >= 25:
            forecast_state = "moderate-change"
        elif score > 0:
            forecast_state = "low-change"

        notes = []

        if len(history) < 2:
            notes.append("Not enough architecture history for trend forecasting yet.")
        else:
            notes.append(f"Route count trend delta: {route_delta}.")
            notes.append(f"Template count trend delta: {template_delta}.")
            notes.append(f"Module count trend delta: {module_delta}.")
            notes.append(f"Static file count trend delta: {static_delta}.")

            if domain_trends:
                notes.append(f"{len(domain_trends)} domain(s) changed across architecture history.")
            else:
                notes.append("No domain-level structural movement detected.")

        return {
            "available": True,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "history_count": len(history),
            "forecast_state": forecast_state,
            "forecast_score": score,
            "summary": {
                "route_delta": route_delta,
                "template_delta": template_delta,
                "module_delta": module_delta,
                "static_delta": static_delta,
                "domain_trend_count": len(domain_trends),
            },
            "domain_trends": domain_trends[:20],
            "trend_notes": notes[:20],
            "safe_mode": True,
            "bounded": True,
            "autonomy": "observation_only",
        }


def build_structural_trend_forecast():
    return StructuralTrendForecaster().build_forecast()
