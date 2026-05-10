from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import subprocess


class RollbackManager:
    """
    Creates safe rollback checkpoints before apply stages.
    Does NOT auto-rollback unless explicitly requested later.
    """

    def __init__(self, project_root="."):
        self.project_root = Path(project_root)

    def create_checkpoint(self) -> Dict[str, Any]:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        try:
            branch = self._current_branch()

            commit = self._current_commit()

            return {
                "status": "checkpoint_created",
                "timestamp": timestamp,
                "branch": branch,
                "commit": commit,
                "rollback_hint": f"git reset --hard {commit}",
                "safe_restore_hint": "git restore .",
            }

        except Exception as exc:
            return {
                "status": "checkpoint_failed",
                "error": str(exc),
            }

    def _current_branch(self) -> str:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
        )

        return result.stdout.strip()

    def _current_commit(self) -> str:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
        )

        return result.stdout.strip()
