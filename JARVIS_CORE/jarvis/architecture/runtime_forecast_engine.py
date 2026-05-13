class RuntimeForecastEngine:
    def analyze(self, memory_data):
        latest = memory_data.get("latest", {}) if isinstance(memory_data, dict) else {}
        evolution = memory_data.get("evolution", {}) if isinstance(memory_data, dict) else {}
        summary = memory_data.get("summary", {}) if isinstance(memory_data, dict) else {}

        hotspot_delta = evolution.get("hotspot_delta", 0)
        cascade_delta = evolution.get("cascade_delta", 0)
        critical_delta = evolution.get("critical_delta", 0)

        snapshots = summary.get("snapshots_recorded", 0)

        top_hotspot = latest.get("top_hotspot", {}) or {}
        top_dependency = latest.get("top_dependency_risk", {}) or {}

        acceleration = self._risk_acceleration(
            hotspot_delta,
            cascade_delta,
            critical_delta
        )

        forecast_state = self._forecast_state(
            acceleration,
            top_dependency.get("score", 0)
        )

        instability = self._instability_probability(
            acceleration,
            top_dependency.get("score", 0),
            snapshots
        )

        return {
            "bounded": True,
            "mode": "predictive_forecasting",
            "autonomous_apply": False,

            "summary": {
                "snapshots_analyzed": snapshots,
                "risk_acceleration": acceleration,
                "forecast_state": forecast_state,
                "instability_probability": instability,
            },

            "top_forecast": {
                "file": top_hotspot.get("file"),
                "risk": top_hotspot.get("risk"),
                "forecast": self._forecast_message(
                    forecast_state,
                    top_hotspot.get("file"),
                    instability
                )
            },

            "forecast_notes": self._forecast_notes(
                forecast_state,
                acceleration,
                instability
            ),
        }

    def _risk_acceleration(self, hotspot_delta, cascade_delta, critical_delta):
        return (
            (hotspot_delta * 2)
            + (cascade_delta * 3)
            + (critical_delta * 4)
        )

    def _forecast_state(self, acceleration, dependency_score):
        if dependency_score >= 90:
            return "critical_watch"

        if acceleration >= 12:
            return "rapid_growth"

        if acceleration >= 5:
            return "moderate_growth"

        return "stable"

    def _instability_probability(self, acceleration, dependency_score, snapshots):
        base = dependency_score / 100

        if acceleration > 0:
            base += acceleration * 0.03

        if snapshots >= 10:
            base += 0.05

        return round(min(base, 1.0), 2)

    def _forecast_message(self, state, file_path, instability):
        if state == "critical_watch":
            return (
                f"{file_path} is under critical architectural watch "
                f"with instability probability {instability}"
            )

        if state == "rapid_growth":
            return (
                f"{file_path} shows rapidly increasing architecture pressure"
            )

        if state == "moderate_growth":
            return (
                f"{file_path} shows moderate architecture growth pressure"
            )

        return (
            f"{file_path} architecture pressure appears stable"
        )

    def _forecast_notes(self, state, acceleration, instability):
        notes = []

        if state == "critical_watch":
            notes.append(
                "High dependency concentration detected in core architecture."
            )

        if acceleration > 0:
            notes.append(
                "Architecture pressure trend is increasing across cognition cycles."
            )

        if instability >= 0.8:
            notes.append(
                "Future modularization planning should be prioritized."
            )

        if not notes:
            notes.append(
                "Architecture trend currently appears stable."
            )

        return notes
