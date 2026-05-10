from pathlib import Path


class UnifiedDiffApplier:
    """
    Applies safe unified diffs to sandbox copies only.
    Original project files are never modified.
    """

    def apply_diff(
        self,
        sandbox_file,
        proposed_content,
    ):
        path = Path(sandbox_file)

        if not path.exists():
            return {
                "status": "missing_target",
                "ok": False,
                "file": str(path),
            }

        original = path.read_text(encoding="utf-8")

        if original == proposed_content:
            return {
                "status": "no_changes",
                "ok": True,
                "file": str(path),
            }

        path.write_text(
            proposed_content,
            encoding="utf-8",
        )

        return {
            "status": "applied",
            "ok": True,
            "file": str(path),
            "modified": True,
        }
