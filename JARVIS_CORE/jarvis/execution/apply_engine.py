from typing import Dict, Any


class ApplyEngine:
    """
    Skeleton only.
    Real patch application is intentionally disabled for safety.
    """

    def prepare_apply(
        self,
        approval_decision: Dict[str, Any],
        patch_validation: Dict[str, Any],
        test_execution: Dict[str, Any],
    ) -> Dict[str, Any]:

        if not approval_decision.get("can_apply"):
            return {
                "status": "blocked",
                "reason": "Approval not granted.",
                "can_apply": False,
            }

        if patch_validation.get("status") == "blocked":
            return {
                "status": "blocked",
                "reason": "Patch validation failed.",
                "can_apply": False,
            }

        if test_execution.get("status") != "passed":
            return {
                "status": "blocked",
                "reason": "Safe tests did not pass.",
                "can_apply": False,
            }

        return {
            "status": "ready_for_controlled_apply",
            "can_apply": False,
            "execution_mode": "manual_only",
            "message": (
                "All safety gates passed. "
                "Real apply engine is intentionally disabled."
            )
        }
