from pathlib import Path
import json

class LearningEvolutionScoringEngine:
    def __init__(self, root="."):
        self.root = Path(root)
        self.memory_dir = self.root / "JARVIS_CORE" / "runtime_memory"
        self.learning_file = self.memory_dir / "learning_memory.jsonl"

    def score(self):
        events = self._read_events()

        if not events:
            return {
                "bounded": True,
                "mode": "learning_evolution_scoring",
                "autonomous_apply": False,
                "summary": {
                    "events_analyzed": 0,
                    "learning_score": 0,
                    "learning_state": "empty",
                    "strategy_stability": "unknown",
                    "cognitive_drift": "unknown",
                },
                "notes": ["No learning events available yet."]
            }

        strategies = [e.get("best_strategy") for e in events if e.get("best_strategy")]
        goals = [e.get("active_goal") for e in events if e.get("active_goal")]
        consensus = [e.get("consensus_state") for e in events if e.get("consensus_state")]
        alignments = [e.get("goal_alignment") for e in events if e.get("goal_alignment")]
        reflections = [int(e.get("reflection_score", 0) or 0) for e in events]

        strategy_stability_score = self._dominance_score(strategies)
        goal_stability_score = self._dominance_score(goals)
        consensus_score = self._strong_ratio(consensus, "strong_consensus")
        alignment_score = self._strong_ratio(alignments, "strong_alignment")
        reflection_score = sum(reflections) / len(reflections) if reflections else 0

        learning_score = round(
            (strategy_stability_score * 0.25)
            + (goal_stability_score * 0.20)
            + (consensus_score * 0.20)
            + (alignment_score * 0.20)
            + (reflection_score * 0.15),
            2
        )

        return {
            "bounded": True,
            "mode": "learning_evolution_scoring",
            "autonomous_apply": False,
            "summary": {
                "events_analyzed": len(events),
                "learning_score": learning_score,
                "learning_state": self._learning_state(learning_score),
                "strategy_stability": self._stability_state(strategy_stability_score),
                "goal_stability": self._stability_state(goal_stability_score),
                "cognitive_drift": self._drift_state(strategy_stability_score, goal_stability_score),
            },
            "signals": {
                "strategy_stability_score": strategy_stability_score,
                "goal_stability_score": goal_stability_score,
                "consensus_score": consensus_score,
                "alignment_score": alignment_score,
                "average_reflection_score": round(reflection_score, 2),
                "top_strategy": self._top_value(strategies),
                "top_goal": self._top_value(goals),
            },
            "recommendation": self._recommendation(learning_score),
            "notes": [
                "Learning evolution scoring evaluates consistency across recorded learning cycles.",
                "This layer is meta-learning only.",
                "No autonomous execution is performed."
            ],
        }

    def _read_events(self):
        if not self.learning_file.exists():
            return []

        rows = []
        for line in self.learning_file.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        return rows

    def _dominance_score(self, values):
        if not values:
            return 0
        top = self._top_value(values)
        return round((values.count(top) / len(values)) * 100, 2)

    def _strong_ratio(self, values, target):
        if not values:
            return 0
        return round((values.count(target) / len(values)) * 100, 2)

    def _top_value(self, values):
        if not values:
            return None
        return max(set(values), key=values.count)

    def _learning_state(self, score):
        if score >= 85:
            return "strong_learning_convergence"
        if score >= 65:
            return "moderate_learning_convergence"
        return "weak_learning_signal"

    def _stability_state(self, score):
        if score >= 85:
            return "stable"
        if score >= 60:
            return "moderate"
        return "unstable"

    def _drift_state(self, strategy_score, goal_score):
        if strategy_score >= 85 and goal_score >= 85:
            return "low"
        if strategy_score >= 60 and goal_score >= 60:
            return "moderate"
        return "high"

    def _recommendation(self, score):
        if score >= 85:
            return "Maintain current bounded learning direction."
        if score >= 65:
            return "Continue learning but monitor strategy drift."
        return "Increase review frequency before relying on learning patterns."
