import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"

PLAN_PATH = MEMORY_DIR / "engineering_planning_refinement.json"
SUPERVISION_PATH = MEMORY_DIR / "execution_supervision_runtime.json"
ROLLBACK_PATH = MEMORY_DIR / "rollback_intelligence_layer.json"

ENGINEERING_MEMORY_PATH = MEMORY_DIR / "autonomous_engineering_memory.json"


def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class AutonomousEngineeringMemory:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        planning = load_json(PLAN_PATH)
        supervision = load_json(SUPERVISION_PATH)
        rollback = load_json(ROLLBACK_PATH)

        refined_plan = planning.get("refined_plan", {})

        memory = {
            "strategy": refined_plan.get("strategy"),
            "target_goal": refined_plan.get("target_goal"),
            "execution_policy": refined_plan.get("execution_policy"),
            "apply_policy": refined_plan.get("apply_policy"),
            "rollback_policy": refined_plan.get("rollback_policy"),
            "supervision_state": supervision.get("supervision_state"),
            "execution_decision": supervision.get("execution_decision"),
            "rollback_state": rollback.get("rollback_state"),
            "rollback_decision": rollback.get("rollback_decision"),
        }

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "autonomous_engineering_memory",
            "bounded": True,
            "dangerous_autonomous_apply": False,
            "memory_mode": "safe_engineering_memory_snapshot",
            "engineering_memory": memory,
            "engineering_state": (
                "guarded_engineering_ready"
                if supervision.get("execution_decision") == "blocked_until_clean_review"
                and rollback.get("rollback_state") == "rollback_ready"
                else "engineering_not_ready"
            ),
            "guardrails": {
                "bounded_execution": True,
                "rollback_required": True,
                "human_review_required": True,
                "autonomous_apply_allowed": False,
            },
            "result": "autonomous_engineering_memory_built",
        }

        ENGINEERING_MEMORY_PATH.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return result


if __name__ == "__main__":
    result = AutonomousEngineeringMemory().build()
    print(json.dumps(result, ensure_ascii=False, indent=2))
