from pathlib import Path
import json

from JARVIS_CORE.jarvis.architecture.task_execution_simulation_engine import TaskExecutionSimulationEngine


class ControlledApplyDecisionEngine:
    def __init__(self, project_root="."):
        self.project_root = Path(project_root)
        self.memory_dir = self.project_root / "JARVIS_CORE/runtime_memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.decision_file = self.memory_dir / "controlled_apply_decision.json"

    def decide(self, objective="safe_architecture_refactor"):
        simulation = TaskExecutionSimulationEngine(self.project_root).simulate(objective)
        summary = simulation.get("summary", {})
        steps = simulation.get("simulated_steps", [])

        avg_confidence = self._average_confidence(steps)
        max_risk = self._max_risk(steps)
        rollback_ready = all(step.get("rollback_ready") for step in steps) if steps else False

        decision = self._decision(summary, avg_confidence, max_risk, rollback_ready)

        payload = {
            "bounded": True,
            "mode": "controlled_apply_decision",
            "autonomous_apply": False,
            "summary": {
                "objective": objective,
                "apply_decision": decision,
                "avg_execution_confidence": avg_confidence,
                "max_risk": max_risk,
                "rollback_ready": rollback_ready,
                "human_approval_required": True,
                "execution_allowed": False
            },
            "approval_plan": {
                "required": True,
                "approval_type": "explicit_human_approval",
                "minimum_checks": [
                    "Review simulated steps",
                    "Confirm rollback readiness",
                    "Confirm target files",
                    "Run py_compile before apply",
                    "Run endpoint smoke tests after apply"
                ]
            },
            "simulation_summary": summary,
            "notes": [
                "Controlled apply decision only determines readiness.",
                "No code changes are applied.",
                "Execution remains disabled until explicit human approval."
            ]
        }

        self.decision_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return payload

    def _average_confidence(self, steps):
        if not steps:
            return 0
        return round(sum(float(s.get("execution_confidence", 0) or 0) for s in steps) / len(steps), 2)

    def _max_risk(self, steps):
        order = {
            "low": 1,
            "low_medium": 2,
            "medium": 3,
            "high": 4,
            "critical": 5,
        }

        risks = [s.get("estimated_risk", "medium") for s in steps]
        if not risks:
            return "unknown"

        return max(risks, key=lambda r: order.get(r, 3))

    def _decision(self, summary, avg_confidence, max_risk, rollback_ready):
        if not rollback_ready:
            return "blocked_missing_rollback"

        if summary.get("chain_feasibility") != "high":
            return "hold_for_review"

        if max_risk in {"high", "critical"}:
            return "blocked_high_risk"

        if avg_confidence >= 90:
            return "ready_for_human_approval"

        return "hold_for_review"
