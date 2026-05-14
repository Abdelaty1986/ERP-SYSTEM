import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"

DIFF_PATH = MEMORY_DIR / "diff_intelligence_runtime.json"
EVOLUTION_PATH = MEMORY_DIR / "evolution_intelligence_layer.json"
PLAN_PATH = MEMORY_DIR / "engineering_planning_refinement.json"


def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class EngineeringPlanningRefinement:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def refine(self):
        diff = load_json(DIFF_PATH)
        evolution = load_json(EVOLUTION_PATH)

        working_tree_clean = diff.get("working_tree_clean", False)
        risk_state = diff.get("risk_state", "unknown")
        evolution_state = evolution.get("evolution_state", "unknown")
        guidance = evolution.get("evolution_guidance", {})

        planning_state = (
            "ready_for_bounded_patch_planning"
            if working_tree_clean and evolution_state == "ready_for_guided_evolution"
            else "requires_review_before_patch_planning"
        )

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "engineering_planning_refinement",
            "bounded": True,
            "dangerous_autonomous_apply": False,
            "planning_mode": "safe_human_review_required_planning",
            "inputs": {
                "working_tree_clean": working_tree_clean,
                "diff_risk_state": risk_state,
                "evolution_state": evolution_state,
                "preferred_strategy": guidance.get("preferred_strategy"),
                "active_goal": guidance.get("active_goal"),
            },
            "planning_state": planning_state,
            "refined_plan": {
                "strategy": guidance.get("preferred_strategy", "bounded_patch_planning"),
                "target_goal": guidance.get("active_goal"),
                "execution_policy": "proposal_only",
                "apply_policy": "human_approval_required",
                "rollback_policy": "checkpoint_required_before_apply",
            },
            "guardrails": {
                "bounded_execution": True,
                "rollback_required": True,
                "human_review_required": True,
                "autonomous_apply_allowed": False,
            },
            "recommendation": (
                "continue_to_execution_supervision"
                if planning_state == "ready_for_bounded_patch_planning"
                else "confirm_clean_tree_then_continue"
            ),
            "result": "engineering_planning_refinement_built",
        }

        PLAN_PATH.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return result


if __name__ == "__main__":
    result = EngineeringPlanningRefinement().refine()
    print(json.dumps(result, ensure_ascii=False, indent=2))
