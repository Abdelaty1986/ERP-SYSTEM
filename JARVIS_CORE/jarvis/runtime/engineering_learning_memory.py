import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"

OUTPUT_PATH = MEMORY_DIR / "engineering_learning_memory.json"
LOG_PATH = LOGS_DIR / "engineering_learning_memory.jsonl"

ENGINEERING_SOURCES = {
    "engineering_planning_refinement": MEMORY_DIR / "engineering_planning_refinement.json",
    "execution_supervision_runtime": MEMORY_DIR / "execution_supervision_runtime.json",
    "human_approved_apply": MEMORY_DIR / "human_approved_apply.json",
    "approved_project_apply_gate": MEMORY_DIR / "controlled_apply_decision.json",
    "project_apply_validation_guard": MEMORY_DIR / "approval_gateway.json",
    "structured_mutation_journal": MEMORY_DIR / "execution_journal.json",
    "rollback_intelligence_layer": MEMORY_DIR / "rollback_intelligence_layer.json",
    "rollback_checkpoint_memory": MEMORY_DIR / "rollback_checkpoint_memory.json",
    "failure_summary": MEMORY_DIR / "failure_summary.json",
}


def load_json(path):
    if not path.exists():
        return {"exists": False, "data": None}

    try:
        return {
            "exists": True,
            "data": json.loads(path.read_text(encoding="utf-8")),
        }
    except Exception as exc:
        return {
            "exists": True,
            "data": None,
            "error": str(exc),
        }


class EngineeringLearningMemory:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        sources = {
            name: load_json(path)
            for name, path in ENGINEERING_SOURCES.items()
        }

        available_sources = [
            name
            for name, payload in sources.items()
            if payload.get("exists") and payload.get("data") is not None
        ]
        missing_sources = [
            name
            for name, payload in sources.items()
            if not payload.get("exists")
        ]
        unreadable_sources = [
            name
            for name, payload in sources.items()
            if payload.get("exists") and payload.get("data") is None
        ]

        planning = sources["engineering_planning_refinement"].get("data") or {}
        supervision = sources["execution_supervision_runtime"].get("data") or {}
        human_apply = sources["human_approved_apply"].get("data") or {}
        failure_summary = sources["failure_summary"].get("data") or {}
        rollback = sources["rollback_intelligence_layer"].get("data") or {}

        controls = supervision.get("execution_controls", {})
        apply_summary = human_apply.get("summary", {})
        refined_plan = planning.get("refined_plan", {})

        engineering_signals = {
            "active_strategy": refined_plan.get("strategy")
            or supervision.get("active_strategy"),
            "active_goal": refined_plan.get("target_goal")
            or supervision.get("active_goal"),
            "planning_state": planning.get("planning_state"),
            "supervision_state": supervision.get("supervision_state"),
            "execution_decision": supervision.get("execution_decision"),
            "apply_state": apply_summary.get("apply_state"),
            "rollback_state": rollback.get("rollback_state"),
            "failure_state": failure_summary.get("failure_state")
            or failure_summary.get("learning_state"),
        }

        learned_constraints = {
            "proposal_only": bool(
                controls.get("proposal_only")
                or refined_plan.get("execution_policy") == "proposal_only"
            ),
            "human_approval_required": True,
            "rollback_required": bool(
                controls.get("rollback_checkpoint_required")
                or planning.get("guardrails", {}).get("rollback_required")
                or human_apply.get("governance", {}).get("rollback_required")
            ),
            "execution_locked": supervision.get("execution_decision")
            == "blocked_until_clean_review"
            or apply_summary.get("execution_allowed") is False,
            "safe_learning_scope": "engineering_outputs_only",
        }

        safety_rules = {
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
        }

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "engineering_learning_memory",
            **safety_rules,
            "memory_mode": "safe_read_only_engineering_learning",
            "phase": "phase_4_runtime_learning_system",
            "layer": "engineering_learning_memory",
            "available_source_count": len(available_sources),
            "available_sources": available_sources,
            "missing_sources": missing_sources,
            "unreadable_sources": unreadable_sources,
            "engineering_signals": engineering_signals,
            "learned_constraints": learned_constraints,
            "learning_assessment": {
                "learning_state": (
                    "stable_learning_ready"
                    if available_sources and not unreadable_sources
                    else "learning_needs_review"
                ),
                "safe_to_inform_future_planning": bool(available_sources)
                and not unreadable_sources,
                "may_execute_recommendations": False,
                "may_apply_changes": False,
            },
            "recommendation": "use_as_memory_input_for_agent_performance_memory",
            "result": "engineering_learning_memory_built",
        }

        OUTPUT_PATH.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.append_log(result)

        return result

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "learning_state": result["learning_assessment"]["learning_state"],
            "available_source_count": result["available_source_count"],
            "execution_allowed": False,
            "apply_allowed": False,
            "human_approval_required": True,
        }

        with LOG_PATH.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    output = EngineeringLearningMemory().build()
    print(json.dumps(output, ensure_ascii=False, indent=2))
