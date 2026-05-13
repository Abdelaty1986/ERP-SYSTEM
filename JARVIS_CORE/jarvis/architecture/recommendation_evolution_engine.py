from collections import Counter

class RecommendationEvolutionEngine:
    def analyze(self, memory_data):
        latest = memory_data.get("latest") or {}
        evolution = memory_data.get("evolution") or {}

        recurring = self._build_recurring_patterns(latest)
        confidence = self._confidence_score(latest, evolution)
        pressure = self._pressure_signals(latest)

        return {
            "bounded": True,
            "mode": "adaptive_recommendation_memory",
            "autonomous_apply": False,
            "summary": {
                "recommendation_confidence": confidence,
                "pressure_signals": len(pressure),
                "recurring_patterns": len(recurring),
                "evolution_state": evolution.get("state", "unknown"),
            },
            "recurring_patterns": recurring,
            "pressure_signals": pressure,
            "recommendation_confidence": {
                "score": confidence,
                "state": self._confidence_state(confidence),
            },
            "notes": [
                "Recommendation evolution is observation-only.",
                "No autonomous refactoring is performed.",
                "Confidence increases with repeated stable observations."
            ],
        }

    def _build_recurring_patterns(self, latest):
        patterns = []

        hotspot = latest.get("top_hotspot") or {}
        priority = latest.get("top_priority") or {}
        dependency = latest.get("top_dependency_risk") or {}

        files = [
            hotspot.get("file"),
            priority.get("file"),
            dependency.get("file"),
        ]

        counter = Counter([x for x in files if x])

        for file_name, count in counter.items():
            patterns.append({
                "file": file_name,
                "occurrences": count,
                "stability": "stable_recurring_signal" if count >= 2 else "weak_signal"
            })

        return patterns

    def _confidence_score(self, latest, evolution):
        base = 40

        top_hotspot = latest.get("top_hotspot") or {}
        top_dependency = latest.get("top_dependency_risk") or {}

        if top_hotspot.get("file") == top_dependency.get("file"):
            base += 25

        if evolution.get("state") == "compared":
            base += 15

        if evolution.get("cascade_delta", 0) == 0:
            base += 10

        return min(base, 100)

    def _pressure_signals(self, latest):
        signals = []

        hotspot = latest.get("top_hotspot") or {}
        dependency = latest.get("top_dependency_risk") or {}

        if hotspot.get("file") == "app.py":
            signals.append({
                "type": "core_concentration",
                "severity": "high",
                "message": "Core application routing concentration remains high."
            })

        if dependency.get("risk") == "high":
            signals.append({
                "type": "cascade_risk",
                "severity": "high",
                "message": "High cascade dependency risk detected."
            })

        return signals

    def _confidence_state(self, score):
        if score >= 80:
            return "strong"
        if score >= 60:
            return "moderate"
        return "weak"
