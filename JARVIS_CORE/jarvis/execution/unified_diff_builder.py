from pathlib import Path
import difflib


class UnifiedDiffBuilder:
    """
    Builds unified diff text from original and proposed content.
    It does not write to project files.
    """

    def build_diff(
        self,
        file_path,
        original_text,
        proposed_text,
        context_lines=3,
    ):
        original_lines = original_text.splitlines(keepends=True)
        proposed_lines = proposed_text.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            proposed_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            n=context_lines,
        )

        return "".join(diff)

    def build_file_diff(
        self,
        file_path,
        proposed_text,
        context_lines=3,
    ):
        path = Path(file_path)

        if not path.exists() or not path.is_file():
            return {
                "status": "missing_file",
                "file_path": str(path),
                "diff": "",
            }

        original_text = path.read_text(encoding="utf-8")

        diff_text = self.build_diff(
            file_path=str(path),
            original_text=original_text,
            proposed_text=proposed_text,
            context_lines=context_lines,
        )

        return {
            "status": "built",
            "file_path": str(path),
            "diff": diff_text,
            "has_changes": bool(diff_text.strip()),
        }
