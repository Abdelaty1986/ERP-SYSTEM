from jarvis.execution.patch_intelligence import PatchIntelligence
from jarvis.execution.unified_diff_validator import UnifiedDiffValidator


class DiffQualityGate:
    """
    Unified decision gate for patch/diff quality.
    It does not apply changes. It only decides whether a diff is safe enough
    to be materialized or moved forward.
    """

    def __init__(self):
        self.patch_intelligence = PatchIntelligence()
        self.diff_validator = UnifiedDiffValidator()

    def evaluate_patch(self, patch):
        intelligence = self.patch_intelligence.analyze_patch(patch)

        file_path = patch.get("file_path", "")
        diff_text = patch.get("diff_preview", "")

        validation = self.diff_validator.validate(
            file_path=file_path,
            diff_text=diff_text,
        )

        issues = []
        issues.extend(intelligence.get("issues", []))
        issues.extend(validation.get("issues", []))

        added = validation.get("added_lines", 0)
        removed = validation.get("removed_lines", 0)

        if issues:
            risk_level = "high"
        elif added > 80 or removed > 40:
            risk_level = "medium"
        else:
            risk_level = "low"

        can_materialize = (
            intelligence.get("can_materialize")
            and validation.get("ok")
            and risk_level in ["low", "medium"]
        )

        return {
            "file_path": file_path,
            "status": "approved" if can_materialize else "blocked",
            "risk_level": risk_level,
            "can_materialize": can_materialize,
            "added_lines": added,
            "removed_lines": removed,
            "issues": issues,
            "intelligence": intelligence,
            "validation": validation,
        }

    def evaluate_plan(self, safe_patch_plan):
        results = []

        for patch in safe_patch_plan.get("patches", []):
            results.append(self.evaluate_patch(patch))

        blocked = [
            item for item in results
            if not item.get("can_materialize")
        ]

        approved = [
            item for item in results
            if item.get("can_materialize")
        ]

        return {
            "status": "passed" if not blocked else "blocked",
            "approved_count": len(approved),
            "blocked_count": len(blocked),
            "results": results,
            "message": (
                "All diffs passed quality gate."
                if not blocked
                else "Some diffs were blocked by quality gate."
            ),
        }
