from pathlib import Path
from datetime import datetime
import json

class GoalPersistenceEngine:
    def __init__(self, root="."):
        self.root = Path(root)
        self.goal_dir = self.root / "JARVIS_CORE" / "runtime_logs"
        self.goal_dir.mkdir(parents=True, exist_ok=True)
        self.goal_file = self.goal_dir / "architecture_goals.json"

    def evaluate(self, deliberation_data):
        goal = self._load_or_create_goal()
        consensus = deliberation_data.get("executive_consensus") or {}
        summary = deliberation_data.get("summary") or {}

        alignment = self._alignment(goal, consensus, summary)

        goal["last_evaluated"] = datetime.utcnow().isoformat() + "Z"
        goal["evaluations"] = goal.get("evaluations", 0) + 1
        goal["last_alignment"] = alignment
        goal["status"] = self._status(alignment)

        self.goal_file.write_text(
            json.dumps(goal, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return {
            "bounded": True,
            "mode": "goal_persistence_only",
            "autonomous_apply": False,
            "summary": {
                "goal_id": goal.get("goal_id"),
                "status": goal.get("status"),
                "evaluations": goal.get("evaluations"),
                "alignment_score": alignment.get("score"),
                "alignment_state": alignment.get("state"),
            },
            "goal": goal,
            "alignment": alignment,
            "notes": [
                "Goal persistence tracks long-horizon architecture intent.",
                "No execution is performed.",
                "Goal updates are observation-only and bounded."
            ],
        }

    def _load_or_create_goal(self):
        if self.goal_file.exists():
            try:
                return json.loads(self.goal_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        return {
            "goal_id": "architecture-pressure-reduction-v1",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "objective": "Reduce app.py architectural pressure safely through bounded blueprint extraction planning.",
            "target": "app.py",
            "desired_strategy": "Blueprint Extraction",
            "safety_mode": "bounded_human_review_required",
            "status": "active",
            "evaluations": 0,
        }

    def _alignment(self, goal, consensus, summary):
        score = 40

        if consensus.get("strategy") == goal.get("desired_strategy"):
            score += 35

        if consensus.get("consensus") == "strong_consensus":
            score += 15

        if summary.get("tensions", 0) <= 1:
            score += 10

        state = "weak"
        if score >= 85:
            state = "strong_alignment"
        elif score >= 65:
            state = "moderate_alignment"

        return {
            "score": min(score, 100),
            "state": state,
            "reason": (
                f"Consensus strategy '{consensus.get('strategy')}' compared "
                f"against persistent goal strategy '{goal.get('desired_strategy')}'."
            )
        }

    def _status(self, alignment):
        if alignment.get("score", 0) >= 85:
            return "on_track"
        if alignment.get("score", 0) >= 65:
            return "watch"
        return "needs_review"
