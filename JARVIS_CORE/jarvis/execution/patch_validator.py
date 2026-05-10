from dataclasses import dataclass, asdict
from typing import List, Dict, Any


@dataclass
class ValidationIssue:
    level: str
    code: str
    message: str
    file_path: str | None = None


class PatchValidator:
    """
    Validates patch proposals before approval/apply.
    It does NOT modify files.
    """

    PROTECTED_BRANCHES = {"main", "master"}

    PROTECTED_PATHS = [
        ".git/",
        ".env",
        "database.db",
        "JARVIS_CORE/memory/jarvis_memory.json",
    ]

    DANGEROUS_PATTERNS = [
        "DROP TABLE",
        "DELETE FROM",
        "TRUNCATE",
        "os.remove",
        "shutil.rmtree",
        "rm -rf",
        "git reset --hard",
        "git push --force",
    ]

    MAX_DIFF_LINES = 250

    def validate(
        self,
        patch_plan: Dict[str, Any],
        git_status: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        issues: List[ValidationIssue] = []

        if not patch_plan:
            issues.append(ValidationIssue(
                level="error",
                code="missing_patch_plan",
                message="No patch plan was provided."
            ))

        git_status = git_status or {}
        branch = git_status.get("branch") or git_status.get("current_branch")

        if branch in self.PROTECTED_BRANCHES:
            issues.append(ValidationIssue(
                level="error",
                code="protected_branch",
                message=f"Patch validation blocked on protected branch: {branch}"
            ))

        for patch in patch_plan.get("patches", []):
            file_path = patch.get("file_path", "")
            diff_preview = patch.get("diff_preview", "")

            self._check_protected_path(file_path, issues)
            self._check_dangerous_patterns(diff_preview, file_path, issues)
            self._check_large_diff(diff_preview, file_path, issues)
            self._check_missing_approval(patch, file_path, issues)

        status = self._status_from_issues(issues)

        return {
            "status": status,
            "can_request_approval": status in {"passed", "warnings"},
            "can_apply": False,
            "issues": [asdict(issue) for issue in issues],
            "summary": self._summary(issues),
        }

    def _check_protected_path(self, file_path: str, issues: List[ValidationIssue]):
        normalized = file_path.replace("\\", "/")

        for protected in self.PROTECTED_PATHS:
            if protected in normalized or normalized.endswith(protected):
                issues.append(ValidationIssue(
                    level="error",
                    code="protected_path",
                    message=f"Protected path cannot be modified: {file_path}",
                    file_path=file_path
                ))

    def _check_dangerous_patterns(
        self,
        diff_preview: str,
        file_path: str,
        issues: List[ValidationIssue]
    ):
        upper_diff = diff_preview.upper()

        for pattern in self.DANGEROUS_PATTERNS:
            if pattern.upper() in upper_diff:
                issues.append(ValidationIssue(
                    level="error",
                    code="dangerous_pattern",
                    message=f"Dangerous operation detected: {pattern}",
                    file_path=file_path
                ))

    def _check_large_diff(
        self,
        diff_preview: str,
        file_path: str,
        issues: List[ValidationIssue]
    ):
        line_count = len(diff_preview.splitlines())

        if line_count > self.MAX_DIFF_LINES:
            issues.append(ValidationIssue(
                level="warning",
                code="large_diff",
                message=f"Large diff detected: {line_count} lines.",
                file_path=file_path
            ))

    def _check_missing_approval(
        self,
        patch: Dict[str, Any],
        file_path: str,
        issues: List[ValidationIssue]
    ):
        if not patch.get("requires_approval", True):
            issues.append(ValidationIssue(
                level="warning",
                code="approval_not_required",
                message="Patch does not explicitly require approval.",
                file_path=file_path
            ))

    def _status_from_issues(self, issues: List[ValidationIssue]) -> str:
        if any(issue.level == "error" for issue in issues):
            return "blocked"
        if any(issue.level == "warning" for issue in issues):
            return "warnings"
        return "passed"

    def _summary(self, issues: List[ValidationIssue]) -> str:
        if not issues:
            return "Patch validation passed with no issues."

        errors = sum(1 for issue in issues if issue.level == "error")
        warnings = sum(1 for issue in issues if issue.level == "warning")

        return f"Validation finished with {errors} error(s) and {warnings} warning(s)."
