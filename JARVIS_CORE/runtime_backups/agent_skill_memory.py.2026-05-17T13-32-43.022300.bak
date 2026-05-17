import json
from pathlib import Path
from datetime import datetime, timezone

MEMORY_PATH = Path("JARVIS_CORE/runtime_memory/agent_skill_memory.json")


class AgentSkillMemory:
    def __init__(self, path=MEMORY_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def load(self):
        if not self.path.exists():
            return {
                "memory_type": "agent_skill_memory",
                "bounded": True,
                "real_apply_enabled": False,
                "agents": {}
            }

        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {
                "memory_type": "agent_skill_memory",
                "bounded": True,
                "real_apply_enabled": False,
                "agents": {},
                "warning": "memory_reset_due_to_read_error"
            }

    def save(self, data):
        data["updated_at"] = self._now()
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def record_agent_result(
        self,
        agent_id,
        skill,
        task_type,
        result_state,
        confidence=0.5,
        notes=None
    ):
        data = self.load()
        agents = data.setdefault("agents", {})

        agent = agents.setdefault(agent_id, {
            "agent_id": agent_id,
            "skills": {},
            "total_runs": 0,
            "success_runs": 0,
            "failure_runs": 0,
            "last_seen": None
        })

        agent.setdefault("skills", {})
        agent.setdefault("total_runs", 0)
        agent.setdefault("success_runs", 0)
        agent.setdefault("failure_runs", 0)
        agent.setdefault("last_seen", None)

        skill_data = agent["skills"].setdefault(skill, {
            "skill": skill,
            "task_types": {},
            "runs": 0,
            "success": 0,
            "failure": 0,
            "confidence_avg": 0.0,
            "last_result": None,
            "notes": []
        })

        task_data = skill_data["task_types"].setdefault(task_type, {
            "runs": 0,
            "success": 0,
            "failure": 0
        })

        success = result_state == "success"

        agent["total_runs"] += 1
        skill_data["runs"] += 1
        task_data["runs"] += 1

        if success:
            agent["success_runs"] += 1
            skill_data["success"] += 1
            task_data["success"] += 1
        else:
            agent["failure_runs"] += 1
            skill_data["failure"] += 1
            task_data["failure"] += 1

        old_avg = skill_data["confidence_avg"]
        runs = skill_data["runs"]
        skill_data["confidence_avg"] = round(
            ((old_avg * (runs - 1)) + confidence) / runs,
            4
        )

        skill_data["last_result"] = result_state
        agent["last_seen"] = self._now()

        if notes:
            skill_data["notes"].append({
                "timestamp": self._now(),
                "note": notes
            })
            skill_data["notes"] = skill_data["notes"][-20:]

        self.save(data)
        return data

    def score_agent(self, agent_id):
        data = self.load()
        agent = data.get("agents", {}).get(agent_id)

        if not agent:
            return {
                "agent_id": agent_id,
                "score": 0.0,
                "state": "unknown"
            }

        total = agent.get("total_runs", 0)

        if total == 0 and agent.get("uses", 0) > 0:
            uses = agent.get("uses", 0)
            successes = agent.get("successes", 0)
            last_score = agent.get("last_score", 0.0)

            success_rate = successes / uses if uses else 0.0
            score = round((success_rate * 0.7) + ((last_score / 100) * 0.3), 4)

            return {
                "agent_id": agent_id,
                "score": score,
                "success_rate": round(success_rate, 4),
                "legacy_score": last_score,
                "total_runs": uses,
                "state": "legacy_scored"
            }

        if total == 0:
            return {
                "agent_id": agent_id,
                "score": 0.0,
                "state": "untrained"
            }

        success_rate = agent.get("success_runs", 0) / total

        skill_confidences = []
        for skill in agent.get("skills", {}).values():
            skill_confidences.append(skill.get("confidence_avg", 0.0))

        avg_confidence = (
            sum(skill_confidences) / len(skill_confidences)
            if skill_confidences else 0.0
        )

        score = round((success_rate * 0.7) + (avg_confidence * 0.3), 4)

        return {
            "agent_id": agent_id,
            "score": score,
            "success_rate": round(success_rate, 4),
            "avg_confidence": round(avg_confidence, 4),
            "total_runs": total,
            "state": "scored"
        }


if __name__ == "__main__":
    memory = AgentSkillMemory()

    memory.record_agent_result(
        agent_id="planner_agent",
        skill="planning",
        task_type="runtime_strategy",
        result_state="success",
        confidence=0.82,
        notes="Initial bounded planning capability recorded."
    )

    memory.record_agent_result(
        agent_id="reviewer_agent",
        skill="validation",
        task_type="runtime_review",
        result_state="success",
        confidence=0.88,
        notes="Initial validation capability recorded."
    )

    print(json.dumps({
        "planner_agent": memory.score_agent("planner_agent"),
        "reviewer_agent": memory.score_agent("reviewer_agent")
    }, ensure_ascii=False, indent=2))


def build_agent_skill_snapshot():
    memory = AgentSkillMemory()
    data = memory.load()
    agents = data.get("agents", {})

    scores = {}
    for agent_id in agents:
        scores[agent_id] = memory.score_agent(agent_id)

    return {
        "snapshot_type": "agent_skill_snapshot",
        "bounded": True,
        "real_apply_enabled": False,
        "agent_count": len(agents),
        "scores": scores,
        "updated_at": data.get("updated_at")
    }


def recommend_agent(skill=None, task_type=None):
    snapshot = build_agent_skill_snapshot()
    data = AgentSkillMemory().load()
    agents = data.get("agents", {})

    candidates = []

    for agent_id, score_data in snapshot.get("scores", {}).items():
        agent = agents.get(agent_id, {})
        score = score_data.get("score", 0.0)

        match_bonus = 0.0

        if skill and skill in agent.get("skills", {}):
            match_bonus += 0.15

        if skill and skill == agent.get("role"):
            match_bonus += 0.1

        if task_type:
            for skill_data in agent.get("skills", {}).values():
                if task_type in skill_data.get("task_types", {}):
                    match_bonus += 0.15

            if task_type in agent.get("best_for", []):
                match_bonus += 0.1

        specialization_multiplier = 1.0

        if match_bonus >= 0.3:
            specialization_multiplier = 1.08
        elif match_bonus >= 0.15:
            specialization_multiplier = 1.04

        final_score = round(
            (score * specialization_multiplier) + match_bonus,
            4
        )

        candidates.append({
            "agent_id": agent_id,
            "base_score": score,
            "match_bonus": round(match_bonus, 4),
            "final_score": final_score,
            "state": score_data.get("state", "unknown")
        })

    candidates.sort(key=lambda item: item["final_score"], reverse=True)

    return {
        "recommendation_type": "agent_skill_recommendation",
        "bounded": True,
        "real_apply_enabled": False,
        "skill": skill,
        "task_type": task_type,
        "recommended_agent": candidates[0] if candidates else None,
        "score_scale": "ranking_score_not_probability",
        "candidates": candidates[:5]
    }
