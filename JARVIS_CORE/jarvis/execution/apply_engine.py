from typing import Dict, Any, Optional

from jarvis.execution.apply_session import ApplySession
from jarvis.execution.sandbox_manager import SandboxManager


class ApplyEngine:
    """
    Controlled apply preparation engine.
    Real patch application is intentionally disabled for safety.

    This engine only prepares an apply session, backups, staging metadata,
    and safety status. It does not modify project source files.
    """

    def __init__(self, root="."):
        self.root = root
        self.sandbox_manager = SandboxManager(root)

    def prepare_apply(
        self,
        approval_decision: Dict[str, Any],
        patch_validation: Dict[str, Any],
        test_execution: Dict[str, Any],
        safe_patch_plan: Optional[Dict[str, Any]] = None,
        task: str = "",
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

        session = ApplySession(task=task or "unspecified task")
        session.mark_validation_passed()
        session.mark_approval_received()
        session.mark_tests_passed()
        session.set_status("simulation_ready")

        staged_targets = []

        if safe_patch_plan:
            for patch in safe_patch_plan.get("patches", []):
                file_path = patch.get("file_path")

                if not file_path:
                    continue

                staged_data = self.sandbox_manager.stage_file(file_path)

                if staged_data:
                    session.add_staged_file(staged_data)
                    staged_targets.append(file_path)

        return {
            "status": "ready_for_controlled_apply",
            "can_apply": False,
            "execution_mode": "simulation_only",
            "message": (
                "All safety gates passed. "
                "Apply simulation session prepared. "
                "Real apply engine is intentionally disabled."
            ),
            "apply_session": session.to_dict(),
            "staged_targets": staged_targets,
        }
