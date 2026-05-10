import subprocess


class GitManager:
    PROTECTED_BRANCHES = {
        "main",
        "master"
    }

    def run(self, *args):
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True
        )

        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }

    def current_branch(self):
        result = self.run("branch", "--show-current")

        if not result["ok"]:
            return None

        return result["stdout"]

    def is_clean(self):
        result = self.run("status", "--porcelain")

        if not result["ok"]:
            return False

        return result["stdout"] == ""

    def branch_is_protected(self):
        branch = self.current_branch()

        return branch in self.PROTECTED_BRANCHES

    def safety_report(self):
        branch = self.current_branch()

        return {
            "current_branch": branch,
            "working_tree_clean": self.is_clean(),
            "protected_branch": self.branch_is_protected(),
            "safe_for_changes": (
                not self.branch_is_protected()
                and self.is_clean()
            )
        }


if __name__ == "__main__":
    manager = GitManager()

    report = manager.safety_report()

    print("Git Safety Report")
    print("=" * 40)

    for key, value in report.items():
        print(f"{key}: {value}")
