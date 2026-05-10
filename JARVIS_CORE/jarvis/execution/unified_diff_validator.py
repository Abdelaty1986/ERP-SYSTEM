class UnifiedDiffValidator:
    """
    Validates unified diff text before any materialization or apply step.
    This validator is conservative by design.
    """

    DANGEROUS_PATTERNS = [
        "rm -rf",
        "os.remove(",
        "shutil.rmtree(",
        "subprocess.Popen(",
        "subprocess.call(",
        "eval(",
        "exec(",
        "DROP TABLE",
        "DELETE FROM",
    ]

    PROTECTED_TARGETS = [
        ".env",
        "database.db",
        "instance/",
        ".git/",
    ]

    def validate(self, file_path, diff_text):
        issues = []

        if not file_path:
            issues.append("Missing file path.")

        if not diff_text or not diff_text.strip():
            issues.append("Empty diff.")

        for target in self.PROTECTED_TARGETS:
            if target in file_path:
                issues.append(f"Protected target blocked: {target}")

        added_lines = []
        removed_lines = []

        for line in diff_text.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                added_lines.append(line)

            if line.startswith("-") and not line.startswith("---"):
                removed_lines.append(line)

        for line in added_lines:
            for pattern in self.DANGEROUS_PATTERNS:
                if pattern in line:
                    issues.append(f"Dangerous pattern detected: {pattern}")

        if len(removed_lines) > 80:
            issues.append("Large deletion detected.")

        if len(added_lines) > 200:
            issues.append("Large insertion detected.")

        return {
            "file_path": file_path,
            "status": "blocked" if issues else "passed",
            "ok": not issues,
            "added_lines": len(added_lines),
            "removed_lines": len(removed_lines),
            "issues": issues,
        }
