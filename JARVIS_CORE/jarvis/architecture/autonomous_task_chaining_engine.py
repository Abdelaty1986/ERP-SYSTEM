from pathlib import Path
import json

from JARVIS_CORE.jarvis.architecture.dynamic_agent_routing_engine import DynamicAgentRoutingEngine


class AutonomousTaskChainingEngine:
    def __init__(self, project_root="."):
        self.project_root = Path(project_root)

        self.memory_dir = self.project_root / "JARVIS_CORE/runtime_memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.chain_file = self.memory_dir / "task_chain_memory.json"

        self.router = DynamicAgentRoutingEngine(project_root)

    def build_chain(self, objective="safe_architecture_refactor"):
        phases = [
            {
                "phase": "planning",
                "task": "Generate bounded execution strategy"
            },
            {
                "phase": "reflection",
                "task": "Review execution safety and coherence"
            },
            {
                "phase": "arbitration",
                "task": "Rank candidate strategies"
            },
            {
                "phase": "learning",
                "task": "Record cognitive learning signals"
            },
            {
                "phase": "failure_guard",
                "task": "Track execution risks and drift"
            }
        ]

        chain = []

        for step in phases:
            routing = self.router.route(step["phase"])

            selected = routing.get("selected_agent", {})

            chain.append({
                "phase": step["phase"],
                "task": step["task"],
                "selected_agent": selected.get("agent_id", "unknown"),
                "routing_score": selected.get("routing_score", 0),
                "state": "planned",
                "bounded": True,
                "autonomous_apply": False
            })

        payload = {
            "bounded": True,
            "mode": "autonomous_task_chaining",
            "autonomous_apply": False,
            "summary": {
                "objective": objective,
                "chain_steps": len(chain),
                "routing_state": "adaptive_chain_ready",
                "execution_mode": "bounded_planning_only"
            },
            "chain": chain,
            "notes": [
                "Task chaining builds bounded execution workflows.",
                "Each phase is routed through adaptive agent selection.",
                "No autonomous execution is performed."
            ]
        }

        self.chain_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return payload
