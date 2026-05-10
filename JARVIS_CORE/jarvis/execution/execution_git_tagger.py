from datetime import datetime
import subprocess


class ExecutionGitTagger:
    """
    Creates local git tags for successful JARVIS execution runs.
    Does not push tags remotely.
    """

    def __init__(self, root="."):
        self.root = root

    def create_tag(
        self,
        enabled=False,
        receipt_id=None,
        commit_hash=None,
        task="",
    ):
        if not enabled:
            return {
                "status": "skipped",
                "ok": True,
                "reason": "tagging_not_enabled",
                "tag": None,
            }

        current_commit = commit_hash or self._current_commit()

        if not current_commit:
            return {
                "status": "blocked",
                "ok": False,
                "reason": "missing_commit_hash",
                "tag": None,
            }

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        tag_name = f"jarvis-run-{timestamp}"

        message = (
            f"JARVIS execution tag\n"
            f"Receipt: {receipt_id or 'none'}\n"
            f"Commit: {current_commit}\n"
            f"Task: {task}\n"
        )

        result = subprocess.run(
            ["git", "tag", "-a", tag_name, current_commit, "-m", message],
            cwd=self.root,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return {
                "status": "failed",
                "ok": False,
                "reason": result.stderr.strip() or result.stdout.strip(),
                "tag": tag_name,
            }

        return {
            "status": "tag_created",
            "ok": True,
            "reason": "execution_tag_created",
            "tag": tag_name,
            "commit": current_commit,
            "receipt_id": receipt_id,
        }

    def _current_commit(self):
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=self.root,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return None

        return result.stdout.strip()
