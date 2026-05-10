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


    def auto_restore_files(
        self,
        checkpoint: Dict[str, Any],
        files,
        reason: str = "",
    ) -> Dict[str, Any]:
        """
        Restore specific files from checkpoint commit.
        This is safer than git reset --hard.
        """

        commit = checkpoint.get("commit")

        if not commit:
            return {
                "status": "rollback_failed",
                "triggered": True,
                "reason": "missing_checkpoint_commit",
                "restored_files": [],
                "failed_files": [],
            }

        restored = []
        failed = []

        for file_path in files or []:
            try:
                result = subprocess.run(
                    ["git", "checkout", commit, "--", str(file_path)],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                )

                if result.returncode == 0:
                    restored.append(str(file_path))
                else:
                    failed.append({
                        "file": str(file_path),
                        "error": result.stderr.strip() or result.stdout.strip(),
                    })

            except Exception as exc:
                failed.append({
                    "file": str(file_path),
                    "error": str(exc),
                })

        return {
            "status": "rollback_completed" if not failed else "rollback_partial_failure",
            "triggered": True,
            "reason": reason,
            "checkpoint": commit,
            "restored_files": restored,
            "failed_files": failed,
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
