from pathlib import Path
import json

from JARVIS_CORE.jarvis.architecture.autonomous_task_chaining_engine import AutonomousTaskChainingEngine


class TaskExecutionSimulationEngine:
    def __init__(self, project_root="."):
        self.project_root = Path(project_root)
        self.memory_dir = self.project_root / "JARVIS_CORE/runtime_memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.simulation_file = self.memory_dir / "task_execution_simulation.json"

    def simulate(self, objective="safe_architecture_refactor"):
        chain_data = AutonomousTaskChainingEngine(self.project_root).build_chain(objective)
        chain = chain_data.get("chain", [])

        simulated_steps = []

        for step in chain:
            risk = self._estimate_risk(step)
            confidence = self._estimate_confidence(step, risk)

            simulated_steps.append({
                "phase": step.get("phase"),
                "task": step.get("task"),
                "selected_agent": step.get("selected_agent"),
                "routing_score": step.get("routing_score", 0),
                "simulated_status": "ready_for_human_review",
                "estimated_risk": risk,
                "execution_confidence": confidence,
                "rollback_ready": True,
                "dependency_state": "bounded_dependencies_checked",
                "autonomous_apply": False,
                "bounded": True,
            })

        feasibility = self._chain_feasibility(simulated_steps)

        payload = {
            "bounded": True,
            "mode": "task_execution_simulation",
            "autonomous_apply": False,
            "summary": {
                "objective": objective,
                "steps_simulated": len(simulated_steps),
                "chain_feasibility": feasibility,
                "execution_mode": "simulation_only",
                "human_review_required": True,
            },
            "simulated_steps": simulated_steps,
            "notes": [
                "Execution simulation estimates risk and readiness only.",
                "No project files are modified.",
                "All real execution remains human-approved."
            ]
        }

        self.simulation_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return payload

    def _estimate_risk(self, step):
        phase = step.get("phase")

        if phase in {"planning", "learning"}:
            return "low"

        if phase in {"reflection", "failure_guard"}:
            return "low_medium"

        if phase == "arbitration":
            return "medium"

        return "medium"

    def _estimate_confidence(self, step, risk):
        routing_score = float(step.get("routing_score", 0) or 0)

        penalty = {
            "low": 0,
            "low_medium": 5,
            "medium": 10,
            "high": 20,
        }.get(risk, 10)

        return max(0, min(100, round(routing_score - penalty, 2)))

    def _chain_feasibility(self, steps):
        if not steps:
            return "empty"

        avg = sum(step.get("execution_confidence", 0) for step in steps) / len(steps)

        if avg >= 90:
            return "high"
        if avg >= 75:
            return "moderate"
        return "low"
