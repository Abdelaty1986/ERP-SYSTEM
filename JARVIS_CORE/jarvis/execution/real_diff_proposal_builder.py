from pathlib import Path

from jarvis.execution.unified_diff_builder import UnifiedDiffBuilder
from jarvis.execution.unified_diff_validator import UnifiedDiffValidator


class RealDiffProposalBuilder:
    """
    Builds minimal real unified diff proposals for safe testing.
    It does not modify original project files.
    """

    def __init__(self):
        self.diff_builder = UnifiedDiffBuilder()
        self.validator = UnifiedDiffValidator()

    def build_safe_comment_diff(self, file_path, task):
        path = Path(file_path)

        if not path.exists() or not path.is_file():
            return {
                "status": "missing_file",
                "file_path": str(path),
                "can_use": False,
                "diff_preview": "",
                "validation": {
                    "status": "blocked",
                    "issues": ["Target file missing."],
                },
            }

        original_text = path.read_text(encoding="utf-8")

        comment = (
            "# JARVIS_SAFE_PROPOSAL: "
            f"{task}\n"
        )

        if "JARVIS_SAFE_PROPOSAL" in original_text:
            proposed_text = original_text
        else:
            proposed_text = comment + original_text

        diff_result = self.diff_builder.build_file_diff(
            file_path=str(path),
            proposed_text=proposed_text,
        )

        validation = self.validator.validate(
            file_path=str(path),
            diff_text=diff_result.get("diff", ""),
        )

        return {
            "status": "built" if validation.get("ok") else "blocked",
            "file_path": str(path),
            "can_use": validation.get("ok"),
            "change_type": "safe_comment_append",
            "risk_level": "low",
            "original_content": original_text,
            "proposed_content": proposed_text,
            "diff_preview": diff_result.get("diff", ""),
            "validation": validation,
        }
