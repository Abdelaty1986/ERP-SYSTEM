from pathlib import Path
from datetime import datetime
import json

class SelfLearningMemoryEngine:
    def __init__(self, root="."):
        self.root = Path(root)
        self.memory_dir = self.root / "JARVIS_CORE" / "runtime_memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.learning_file = self.memory_dir / "learning_memory.jsonl"
        self.summary_file = self.memory_dir / "learning_summary.json"

    def learn(self, identity_data, goal_data, deliberation_data, arbitration_data, reflection_data):
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "bounded": True,
            "mode": "self_learning_memory",
            "autonomous_apply": False,
            "active_goal": self._get(goal_data, ["summary", "goal_id"]),
            "goal_status": self._get(goal_data, ["summary", "status"]),
            "goal_alignment": self._get(goal_data, ["summary", "alignment_state"]),
            "runtime_mode": self._get(identity_data, ["identity", "operational_mode"]),
            "continuity_state": self._get(identity_data, ["continuity", "state"]),
            "consensus_state": self._get(deliberation_data, ["summary", "consensus_state"]),
            "best_strategy": self._get(arbitration_data, ["summary", "best_strategy"]),
            "reflection_score": self._get(reflection_data, ["summary", "reflection_score"]),
            "lesson": self._build_lesson(identity_data, goal_data, deliberation_data, arbitration_data, reflection_data),
        }

        with self.learning_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

        summary = self._build_summary()
        self.summary_file.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return {
            "bounded": True,
            "mode": "self_learning_memory",
            "autonomous_apply": False,
            "learning_event": event,
            "summary": summary,
            "notes": [
                "Self-learning memory stores lessons from cognitive cycles.",
                "It does not execute actions.",
                "Learning is observational and bounded."
            ],
        }

    def _build_summary(self):
        events = self._read_events()
        strategies = {}
        goals = {}

        for event in events:
            strategy = event.get("best_strategy") or "unknown"
            goal = event.get("active_goal") or "unknown"

            strategies[strategy] = strategies.get(strategy, 0) + 1
            goals[goal] = goals.get(goal, 0) + 1

        top_strategy = max(strategies, key=strategies.get) if strategies else None
        top_goal = max(goals, key=goals.get) if goals else None

        return {
            "events_recorded": len(events),
            "top_strategy": top_strategy,
            "top_goal": top_goal,
            "strategy_frequency": strategies,
            "goal_frequency": goals,
            "learning_state": "active" if events else "empty",
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

    def _build_lesson(self, identity_data, goal_data, deliberation_data, arbitration_data, reflection_data):
        best_strategy = self._get(arbitration_data, ["summary", "best_strategy"])
        consensus = self._get(deliberation_data, ["summary", "consensus_state"])
        alignment = self._get(goal_data, ["summary", "alignment_state"])
        reflection_score = self._get(reflection_data, ["summary", "reflection_score"])

        return (
            f"When goal alignment is {alignment}, consensus is {consensus}, "
            f"and reflection score is {reflection_score}, strategy '{best_strategy}' "
            f"remains the preferred bounded planning direction."
        )

    def _get(self, data, path, default=None):
        current = data
        for key in path:
            if not isinstance(current, dict):
                return default
            current = current.get(key)
        return current if current is not None else default
