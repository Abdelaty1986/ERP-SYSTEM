import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"

PLAN_PATH = MEMORY_DIR / "engineering_planning_refinement.json"
SUPERVISION_PATH = MEMORY_DIR / "execution_supervision_runtime.json"


def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class ExecutionSupervisionRuntime:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def supervise(self):
        planning = load_json(PLAN_PATH)

        planning_state = planning.get("planning_state")
        refined_plan = planning.get("refined_plan", {})

        supervision_state = (
            "execution_locked_pending_review"
            if planning_state != "ready_for_bounded_patch_planning"
            else "execution_ready_but_guarded"
        )

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "execution_supervision_runtime",
            "bounded": True,
            "dangerous_autonomous_apply": False,
            "supervision_mode": "safe_execution_supervision",
            "planning_state": planning_state,
            "supervision_state": supervision_state,
            "execution_controls": {
                "proposal_only": True,
                "human_approval_required": True,
                "rollback_checkpoint_required": True,
                "autonomous_apply_allowed": False,
                "runtime_monitoring_required": True,
            },
            "active_strategy": refined_plan.get("strategy"),
            "active_goal": refined_plan.get("target_goal"),
            "execution_decision": (
                "blocked_until_clean_review"
                if supervision_state == "execution_locked_pending_review"
                else "guarded_execution_allowed"
            ),
            "result": "execution_supervision_built",
        }

        SUPERVISION_PATH.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return result


if __name__ == "__main__":
    result = ExecutionSupervisionRuntime().supervise()
    print(json.dumps(result, ensure_ascii=False, indent=2))
