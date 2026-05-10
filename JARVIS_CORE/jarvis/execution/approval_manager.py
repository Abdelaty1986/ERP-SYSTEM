from dataclasses import dataclass, asdict
from typing import Dict, Any


@dataclass
class ApprovalDecision:
    status: str
    can_request_approval: bool
    can_apply: bool
    requires_human_approval: bool
    message: str


class ApprovalManager:
    """
    Controls human approval state before any patch can be applied.
    It does NOT apply patches.
    """

    def evaluate(
        self,
        patch_plan: Dict[str, Any],
        patch_validation: Dict[str, Any],
        human_approval: str | None = None,
    ) -> Dict[str, Any]:
        validation_status = patch_validation.get("status")

        if validation_status == "blocked":
            return asdict(ApprovalDecision(
                status="blocked_by_validation",
                can_request_approval=False,
                can_apply=False,
                requires_human_approval=True,
                message="Patch is blocked by validation errors."
            ))

        if not patch_plan:
            return asdict(ApprovalDecision(
                status="missing_patch_plan",
                can_request_approval=False,
                can_apply=False,
                requires_human_approval=True,
                message="No patch plan exists."
            ))

        if human_approval is None:
            return asdict(ApprovalDecision(
                status="waiting_for_human_approval",
                can_request_approval=True,
                can_apply=False,
                requires_human_approval=True,
                message="Patch proposal is valid but waiting for human approval."
            ))

        normalized = str(human_approval).strip().lower()

        if normalized in {"approve", "approved", "yes", "y", "موافق", "نفذ"}:
            return asdict(ApprovalDecision(
                status="approved",
                can_request_approval=False,
                can_apply=True,
                requires_human_approval=False,
                message="Human approval received. Patch can move to apply stage."
            ))

        if normalized in {"reject", "rejected", "no", "n", "رفض", "لا"}:
            return asdict(ApprovalDecision(
                status="rejected",
                can_request_approval=False,
                can_apply=False,
                requires_human_approval=False,
                message="Human rejected the patch proposal."
            ))

        return asdict(ApprovalDecision(
            status="unknown_approval_response",
            can_request_approval=True,
            can_apply=False,
            requires_human_approval=True,
            message="Approval response was not recognized."
        ))
