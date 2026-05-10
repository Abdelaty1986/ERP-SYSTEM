import subprocess
from datetime import datetime


class EphemeralBranchManager:
    """
    Creates isolated temporary branches for JARVIS execution runs.
    Does not merge automatically.
    """

    def __init__(self, root="."):
        self.root = root

    def create_branch(self, enabled=False, session_id=None):
        if not enabled:
            return {
                "status": "skipped",
                "ok": True,
                "reason": "ephemeral_branching_not_enabled",
                "branch": None,
            }

        base_branch = self._current_branch()

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        suffix = session_id or timestamp
        branch_name = f"jarvis-exec-{suffix}"[:80]

        result = subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=self.root,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return {
                "status": "failed",
                "ok": False,
                "reason": result.stderr.strip() or result.stdout.strip(),
                "branch": branch_name,
                "base_branch": base_branch,
            }

        return {
            "status": "branch_created",
            "ok": True,
            "reason": "isolated_execution_branch_created",
            "branch": branch_name,
            "base_branch": base_branch,
        }

    def return_to_base(self, branch_result):
        base_branch = branch_result.get("base_branch")

        if not base_branch:
            return {
                "status": "skipped",
                "ok": True,
                "reason": "no_base_branch",
            }

        result = subprocess.run(
            ["git", "checkout", base_branch],
            cwd=self.root,
            capture_output=True,
            text=True,
        )

        return {
            "status": "returned_to_base" if result.returncode == 0 else "failed",
            "ok": result.returncode == 0,
            "base_branch": base_branch,
            "reason": result.stderr.strip() or result.stdout.strip(),
        }

    def _current_branch(self):
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=self.root,
            capture_output=True,
            text=True,
        )

        return result.stdout.strip() or "unknown"
