import subprocess
from pathlib import Path


class RealApplyPolicyManager:
    """
    Final safety gate before applying changes to real project files.
    Default mode is simulation_only.
    """

    ALLOWED_MODES = {
        "simulation_only",
        "gated_apply",
    }

    PROTECTED_BRANCHES = {
        "main",
        "master",
        "production",
    }

    def __init__(self, root="."):
        self.root = Path(root).resolve()

    def evaluate(
        self,
        mode="simulation_only",
        human_confirmed=False,
        tests_passed=False,
        sandbox_passed=False,
        receipt_generated=False,
        audit_recorded=False,
        rollback_checkpoint_created=False,
    ):
        branch = self._current_branch()

        if mode not in self.ALLOWED_MODES:
            return self._blocked("invalid_real_apply_mode", mode, branch)

        if mode == "simulation_only":
            return self._blocked("simulation_only_policy", mode, branch)

        if branch in self.PROTECTED_BRANCHES:
            return self._blocked("protected_branch_blocked", mode, branch)

        if not human_confirmed:
            return self._blocked("human_confirmation_required", mode, branch)

        if not tests_passed:
            return self._blocked("tests_not_passed", mode, branch)

        if not sandbox_passed:
            return self._blocked("sandbox_not_passed", mode, branch)

        if not receipt_generated:
            return self._blocked("receipt_not_generated", mode, branch)

        if not audit_recorded:
            return self._blocked("audit_not_recorded", mode, branch)

        if not rollback_checkpoint_created:
            return self._blocked("rollback_checkpoint_required", mode, branch)

        return {
            "status": "allowed",
            "ok": True,
            "mode": mode,
            "branch": branch,
            "reason": "all_real_apply_gates_passed",
            "can_apply_real_files": True,
        }

    def _blocked(self, reason, mode, branch):
        return {
            "status": "blocked",
            "ok": False,
            "mode": mode,
            "branch": branch,
            "reason": reason,
            "can_apply_real_files": False,
        }

    def _current_branch(self):
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() or "unknown"
