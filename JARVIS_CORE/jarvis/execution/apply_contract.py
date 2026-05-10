from dataclasses import dataclass, asdict
from typing import Dict, Any, List


@dataclass
class ApplyRule:
    rule_id: str
    description: str
    required: bool = True


class ControlledApplyContract:
    """
    Defines mandatory safety rules before real patch apply.
    Real apply is still disabled.
    """

    def __init__(self):
        self.rules: List[ApplyRule] = [
            ApplyRule(
                "approval_required",
                "Human approval must exist."
            ),
            ApplyRule(
                "validation_required",
                "Patch validation must pass."
            ),
            ApplyRule(
                "tests_required",
                "Safe tests must pass."
            ),
            ApplyRule(
                "rollback_checkpoint_required",
                "Rollback checkpoint must exist."
            ),
            ApplyRule(
                "protected_branch_block",
                "Protected branches cannot receive direct apply."
            ),
        ]

    def evaluate(
        self,
        approval_decision: Dict[str, Any],
        patch_validation: Dict[str, Any],
        test_execution: Dict[str, Any],
        rollback_checkpoint: Dict[str, Any],
        git_branch: str = "",
    ) -> Dict[str, Any]:

        violations = []

        if not approval_decision.get("can_apply"):
            violations.append(
                "Human approval missing."
            )

        if patch_validation.get("status") == "blocked":
            violations.append(
                "Patch validation failed."
            )

        if test_execution.get("status") != "passed":
            violations.append(
                "Safe tests did not pass."
            )

        if rollback_checkpoint.get("status") != "checkpoint_created":
            violations.append(
                "Rollback checkpoint missing."
            )

        if git_branch in {"main", "master"}:
            violations.append(
                f"Direct apply blocked on protected branch: {git_branch}"
            )

        return {
            "status": (
                "contract_passed"
                if not violations
                else "contract_blocked"
            ),
            "can_apply_for_real": False,
            "real_apply_enabled": False,
            "violations": violations,
            "rules": [
                asdict(rule)
                for rule in self.rules
            ],
            "message": (
                "Controlled apply contract passed."
                if not violations
                else "Controlled apply contract blocked."
            )
        }
