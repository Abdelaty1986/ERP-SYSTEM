class PatchIntelligence:
    """
    Analyzes patch proposals before materialization.
    It detects placeholder diffs, weak proposals, and unsafe targets.
    """

    PLACEHOLDER_MARKERS = [
        "No automatic code changes generated yet",
        "Next phase will connect AI-generated diffs here",
        "Proposed safe update for",
    ]

    def analyze_patch(self, patch):
        diff_preview = patch.get("diff_preview", "")
        file_path = patch.get("file_path", "")

        issues = []

        if not file_path:
            issues.append("Missing file path.")

        if not diff_preview.strip():
            issues.append("Missing diff preview.")

        for marker in self.PLACEHOLDER_MARKERS:
            if marker in diff_preview:
                issues.append("Patch is placeholder-only.")
                break

        if file_path.endswith("/"):
            issues.append("Patch target is a directory, not a file.")

        return {
            "file_path": file_path,
            "status": "weak" if issues else "strong",
            "can_materialize": not issues,
            "issues": issues,
        }

    def analyze_plan(self, safe_patch_plan):
        results = []

        for patch in safe_patch_plan.get("patches", []):
            results.append(self.analyze_patch(patch))

        weak = [
            item for item in results
            if item.get("status") != "strong"
        ]

        return {
            "status": "passed" if not weak else "needs_real_diff",
            "strong_count": len(results) - len(weak),
            "weak_count": len(weak),
            "results": results,
            "message": (
                "Patch intelligence passed."
                if not weak
                else "Patch plan contains placeholder or weak diffs."
            ),
        }
