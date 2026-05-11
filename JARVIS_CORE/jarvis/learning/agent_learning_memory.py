from pathlib import Path
from datetime import datetime
import json


class AgentLearningMemory:
    def __init__(self, memory_path=None):
        self.memory_path = Path(memory_path or "JARVIS_CORE/runtime_logs/agent_learning_memory.json")
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)

    def _empty(self):
        return {
            "agents": {},
            "updated_at": None,
        }

    def load(self):
        if not self.memory_path.exists():
            return self._empty()

        try:
            return json.loads(self.memory_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return self._empty()

    def save(self, data):
        data["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.memory_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return data

    def record_result(self, agent_id, task_type="general", success=False, duration_seconds=None, safety_score=None):
        data = self.load()

        agent = data["agents"].setdefault(agent_id, {
            "total_runs": 0,
            "successes": 0,
            "failures": 0,
            "task_types": {},
            "avg_duration_seconds": None,
            "avg_safety_score": None,
            "last_result": None,
            "last_seen": None,
        })

        agent["total_runs"] += 1
        if success:
            agent["successes"] += 1
        else:
            agent["failures"] += 1

        task_stats = agent["task_types"].setdefault(task_type, {
            "runs": 0,
            "successes": 0,
            "failures": 0,
        })

        task_stats["runs"] += 1
        if success:
            task_stats["successes"] += 1
        else:
            task_stats["failures"] += 1

        if duration_seconds is not None:
            old = agent["avg_duration_seconds"]
            agent["avg_duration_seconds"] = duration_seconds if old is None else round((old + duration_seconds) / 2, 3)

        if safety_score is not None:
            old = agent["avg_safety_score"]
            agent["avg_safety_score"] = safety_score if old is None else round((old + safety_score) / 2, 3)

        agent["last_result"] = "success" if success else "failure"
        agent["last_seen"] = datetime.now().isoformat(timespec="seconds")

        return self.save(data)

    def rank_agents(self, task_type=None):
        data = self.load()
        ranked = []

        for agent_id, stats in data.get("agents", {}).items():
            total = stats.get("total_runs", 0)
            success_rate = (stats.get("successes", 0) / total) if total else 0

            if task_type and task_type in stats.get("task_types", {}):
                task = stats["task_types"][task_type]
                task_total = task.get("runs", 0)
                success_rate = (task.get("successes", 0) / task_total) if task_total else success_rate

            safety = stats.get("avg_safety_score")
            duration = stats.get("avg_duration_seconds")

            score = success_rate
            if safety is not None:
                score += safety / 10
            if duration is not None and duration > 0:
                score += min(1 / duration, 0.2)

            ranked.append({
                "agent_id": agent_id,
                "score": round(score, 4),
                "success_rate": round(success_rate, 4),
                "total_runs": total,
                "avg_duration_seconds": duration,
                "avg_safety_score": safety,
                "last_result": stats.get("last_result"),
            })

        return sorted(ranked, key=lambda x: x["score"], reverse=True)

    def best_agent(self, task_type=None):
        ranked = self.rank_agents(task_type=task_type)
        return ranked[0] if ranked else None
