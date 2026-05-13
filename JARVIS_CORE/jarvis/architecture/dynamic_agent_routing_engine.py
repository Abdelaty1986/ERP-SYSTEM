from pathlib import Path
import json

from jarvis.runtime.agent_skill_memory import recommend_agent


class DynamicAgentRoutingEngine:
    def __init__(self, project_root="."):
        self.project_root = Path(project_root)
        self.memory_dir = self.project_root / "JARVIS_CORE/runtime_memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.skill_file = self.memory_dir / "agent_skill_memory.json"
        self.routing_file = self.memory_dir / "agent_routing_memory.json"

    def _load_skills(self):
        if not self.skill_file.exists():
            return []

        try:
            data = json.loads(self.skill_file.read_text(encoding="utf-8"))
            agents = data.get("agents", [])

            if isinstance(agents, dict):
                normalized = []
                for agent_id, agent_data in agents.items():
                    if isinstance(agent_data, dict):
                        item = dict(agent_data)
                        item["agent_id"] = agent_id
                        item["skill_score"] = item.get("last_score", item.get("skill_score", 0))
                        item["state"] = item.get("last_state", item.get("state", "unknown"))
                        normalized.append(item)
                return normalized

            if isinstance(agents, list):
                return agents

            return []
        except Exception:
            return []

    def route(self, task_type="planning"):
        try:
            unified = recommend_agent(skill=task_type, task_type=task_type)
            selected_unified = unified.get("recommended_agent") or {}

            if selected_unified.get("agent_id"):
                payload = self._route_with_unified_recommendation(
                    task_type=task_type,
                    unified=unified,
                )

                self.routing_file.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )

                return payload
        except Exception:
            pass

        agents = self._load_skills()

        if not agents:
            return {
                "bounded": True,
                "mode": "dynamic_agent_routing",
                "autonomous_apply": False,
                "state": "no_agents_available"
            }

        scored = []

        for agent in agents:
            score = float(agent.get("skill_score", 0))

            role = agent.get("role", "")

            routing_bonus = 0

            preferred = {
                "planning": "planning",
                "reflection": "reflection",
                "arbitration": "arbitration",
                "learning": "learning",
                "failure_guard": "failure_guard",
            }

            if preferred.get(task_type) == role:
                routing_bonus += 25
            elif task_type in role:
                routing_bonus += 10

            role_match = 1 if preferred.get(task_type) == role else 0
            final_score = min(score + routing_bonus, 100)

            scored.append({
                **agent,
                "routing_score": final_score,
                "role_match": role_match
            })

        scored.sort(
            key=lambda x: (x["role_match"], x["routing_score"]),
            reverse=True
        )

        selected = scored[0]

        payload = {
            "bounded": True,
            "mode": "dynamic_agent_routing",
            "autonomous_apply": False,
            "summary": {
                "task_type": task_type,
                "agents_evaluated": len(scored),
                "selected_agent": selected["agent_id"],
                "routing_score": selected["routing_score"],
                "routing_state": "adaptive_routing_active"
            },
            "selected_agent": {
                "agent_id": selected["agent_id"],
                "role": selected["role"],
                "routing_score": selected["routing_score"],
                "skill_score": selected["skill_score"],
                "best_for": selected.get("best_for", []),
                "state": selected.get("state", "active")
            },
            "ranked_agents": scored,
            "notes": [
                "Dynamic routing selects the strongest agent for the requested task type.",
                "Routing remains bounded and human-governed.",
                "No autonomous execution is performed."
            ]
        }

        self.routing_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return payload


def _dynamic_route_with_unified_recommendation(self, task_type, unified):
    candidates = unified.get("candidates", [])
    selected = unified.get("recommended_agent") or {}

    ranked_agents = []

    for candidate in candidates:
        ranking_score = float(candidate.get("final_score", 0) or 0)
        routing_score = round(min(ranking_score * 100, 100), 2)

        ranked_agents.append({
            "agent_id": candidate.get("agent_id"),
            "routing_score": routing_score,
            "ranking_score": ranking_score,
            "base_score": candidate.get("base_score", 0),
            "match_bonus": candidate.get("match_bonus", 0),
            "state": candidate.get("state", "unknown"),
            "role_match": 1 if candidate.get("match_bonus", 0) else 0,
            "source": "runtime.agent_skill_memory.recommend_agent"
        })

    selected_score = round(
        min(float(selected.get("final_score", 0) or 0) * 100, 100),
        2
    )

    return {
        "bounded": True,
        "mode": "dynamic_agent_routing",
        "routing_source": "unified_recommend_agent",
        "autonomous_apply": False,
        "real_apply_enabled": False,
        "execution_allowed": False,
        "summary": {
            "task_type": task_type,
            "agents_evaluated": len(ranked_agents),
            "selected_agent": selected.get("agent_id"),
            "routing_score": selected_score,
            "routing_state": "adaptive_routing_active"
        },
        "selected_agent": {
            "agent_id": selected.get("agent_id"),
            "routing_score": selected_score,
            "ranking_score": selected.get("final_score", 0),
            "state": selected.get("state", "unknown"),
            "source": "runtime.agent_skill_memory.recommend_agent"
        },
        "ranked_agents": ranked_agents,
        "notes": [
            "Dynamic routing uses the unified runtime recommendation interface.",
            "Legacy routing fallback remains available if unified recommendation fails.",
            "No autonomous execution is performed."
        ]
    }


DynamicAgentRoutingEngine._route_with_unified_recommendation = (
    _dynamic_route_with_unified_recommendation
)
