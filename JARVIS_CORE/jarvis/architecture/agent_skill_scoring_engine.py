from pathlib import Path
from datetime import datetime
import json

class AgentSkillScoringEngine:
    def __init__(self, root="."):
        self.root = Path(root)
        self.memory_dir = self.root / "JARVIS_CORE" / "runtime_memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.skill_file = self.memory_dir / "agent_skill_memory.json"

    def evaluate(self):
        agents = self._load_agents()

        agent_scores = []
        for agent_id, data in agents.items():
            score = self._score(data)
            agent_scores.append({
                "agent_id": agent_id,
                "role": data.get("role"),
                "successes": data.get("successes", 0),
                "failures": data.get("failures", 0),
                "uses": data.get("uses", 0),
                "skill_score": score,
                "state": self._state(score),
                "best_for": data.get("best_for", []),
                "bounded": True,
                "mode": "agent_skill_scoring",
                "autonomous_apply": False,
            })

        agent_scores.sort(key=lambda x: x["skill_score"], reverse=True)
        best = agent_scores[0] if agent_scores else None

        result = {
            "bounded": True,
            "mode": "agent_skill_scoring",
            "autonomous_apply": False,
            "summary": {
                "agents_tracked": len(agent_scores),
                "best_agent": best.get("agent_id") if best else None,
                "best_score": best.get("skill_score") if best else 0,
                "routing_state": "ready" if agent_scores else "empty",
            },
            "agents": agent_scores,
            "recommendation": self._recommendation(best),
            "notes": [
                "Agent skill scoring estimates which cognitive role is strongest.",
                "This layer does not route or execute tasks yet.",
                "Future orchestration must remain bounded and human-governed."
            ],
        }

        self.skill_file.write_text(
            json.dumps(self._to_memory(result), ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return result

    def _load_agents(self):
        if self.skill_file.exists():
            try:
                data = json.loads(self.skill_file.read_text(encoding="utf-8"))
                if isinstance(data.get("agents"), dict):
                    return data["agents"]
            except Exception:
                pass

        return {
            "planner_agent": {
                "role": "planning",
                "uses": 5,
                "successes": 5,
                "failures": 0,
                "best_for": ["strategy_planning", "safe_execution_plans"]
            },
            "reflection_agent": {
                "role": "reflection",
                "uses": 5,
                "successes": 5,
                "failures": 0,
                "best_for": ["self_review", "safety_alignment"]
            },
            "arbitration_agent": {
                "role": "arbitration",
                "uses": 4,
                "successes": 4,
                "failures": 0,
                "best_for": ["strategy_ranking", "tradeoff_balancing"]
            },
            "learning_agent": {
                "role": "learning",
                "uses": 3,
                "successes": 3,
                "failures": 0,
                "best_for": ["memory_scoring", "learning_evolution"]
            },
            "failure_guard_agent": {
                "role": "failure_guard",
                "uses": 2,
                "successes": 2,
                "failures": 0,
                "best_for": ["risk_memory", "failure_pattern_tracking"]
            }
        }

    def _score(self, data):
        uses = int(data.get("uses", 0) or 0)
        successes = int(data.get("successes", 0) or 0)
        failures = int(data.get("failures", 0) or 0)

        if uses <= 0:
            return 0

        success_ratio = successes / uses
        failure_penalty = failures * 10
        experience_bonus = min(uses * 3, 15)

        score = round((success_ratio * 85) + experience_bonus - failure_penalty, 2)
        return max(0, min(score, 100))

    def _state(self, score):
        if score >= 90:
            return "expert"
        if score >= 75:
            return "reliable"
        if score >= 50:
            return "developing"
        return "needs_review"

    def _recommendation(self, best):
        if not best:
            return "No agent skill data available yet."
        return f"Prefer {best.get('agent_id')} for {best.get('role')} tasks under human-governed routing."

    def _to_memory(self, result):
        agents = {}
        for item in result.get("agents", []):
            agents[item["agent_id"]] = {
                "role": item.get("role"),
                "uses": item.get("uses"),
                "successes": item.get("successes"),
                "failures": item.get("failures"),
                "best_for": item.get("best_for", []),
                "last_score": item.get("skill_score"),
                "last_state": item.get("state"),
                "updated_at": datetime.utcnow().isoformat() + "Z",
            }
        return {"agents": agents}
