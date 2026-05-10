import subprocess
from pathlib import Path


class GitCommitEngine:
    """
    Safe local git commit engine for approved JARVIS runtime sessions.
    Does not push remotely.
    """

    BLOCKED_PARTS = {
        ".git",
        "__pycache__",
        ".env",
        "venv",
        ".venv",
        "node_modules",
    }

    def __init__(self, root="."):
        self.root = Path(root).resolve()

    def create_commit(
        self,
        message,
        files=None,
        real_apply_enabled=False,
        tests_passed=False,
        sandbox_passed=False,
        receipt_generated=False,
        audit_recorded=False,
    ):
        files = files or []

        if not real_apply_enabled:
            return self._blocked("real_apply_switch_disabled", files)

        if not tests_passed:
            return self._blocked("tests_not_passed", files)

        if not sandbox_passed:
            return self._blocked("sandbox_not_passed", files)

        if not receipt_generated:
            return self._blocked("receipt_not_generated", files)

        if not audit_recorded:
            return self._blocked("audit_not_recorded", files)

        safe_files = []
        unsafe_files = []

        for file_path in files:
            path = Path(file_path)

            if self._is_unsafe(path):
                unsafe_files.append(str(path))
                continue

            full_path = (self.root / path).resolve()

            if full_path.exists():
                safe_files.append(str(path))

        if unsafe_files:
            return {
                "status": "blocked",
                "ok": False,
                "reason": "unsafe_files_detected",
                "unsafe_files": unsafe_files,
                "files": files,
            }

        if not safe_files:
            return {
                "status": "nothing_to_commit",
                "ok": True,
                "reason": "no_safe_files",
                "files": [],
            }

        for file_path in safe_files:
            subprocess.run(
                ["git", "add", file_path],
                cwd=self.root,
                capture_output=True,
                text=True,
            )

        diff_check = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=self.root,
            capture_output=True,
            text=True,
        )

        staged_files = [
            line.strip()
            for line in diff_check.stdout.splitlines()
            if line.strip()
        ]

        if not staged_files:
            return {
                "status": "nothing_to_commit",
                "ok": True,
                "reason": "no_staged_changes",
                "files": safe_files,
            }

        commit = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=self.root,
            capture_output=True,
            text=True,
        )

        if commit.returncode != 0:
            return {
                "status": "failed",
                "ok": False,
                "files": staged_files,
                "stdout": commit.stdout,
                "stderr": commit.stderr,
                "message": message,
            }

        commit_hash = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=self.root,
            capture_output=True,
            text=True,
        ).stdout.strip()

        return {
            "status": "committed",
            "ok": True,
            "commit_hash": commit_hash,
            "files": staged_files,
            "stdout": commit.stdout,
            "stderr": commit.stderr,
            "message": message,
        }

    def _blocked(self, reason, files):
        return {
            "status": "blocked",
            "ok": False,
            "reason": reason,
            "files": files or [],
        }

    def _is_unsafe(self, path):
        if set(path.parts) & self.BLOCKED_PARTS:
            return True

        full_path = (self.root / path).resolve()
        return not str(full_path).startswith(str(self.root))
