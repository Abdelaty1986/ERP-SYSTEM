from dataclasses import dataclass, asdict
from typing import List, Dict, Any
from pathlib import Path
import difflib


@dataclass
class ProposedPatch:
    file_path: str
    change_type: str
    risk_level: str
    reason: str
    diff_preview: str
    requires_approval: bool = True


class SafePatchGenerator:
    """
    Generates safe patch proposals only.
    It does NOT write, delete, rename, or modify files.
    """

    DANGEROUS_KEYWORDS = [
        "delete",
        "remove database",
        "drop table",
        "reset database",
        "overwrite",
        "force push",
        "main",
        "master",
    ]

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)

    def generate_patch_plan(
        self,
        task: str,
        expected_files: List[str],
        inspections: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        inspections = inspections or {}

        risk_level = self._estimate_risk(task, expected_files)
        change_type = self._guess_change_type(task)

        patches: List[ProposedPatch] = []

        for file_path in expected_files:
            patch = self._build_placeholder_patch(
                task=task,
                file_path=file_path,
                change_type=change_type,
                risk_level=risk_level,
                inspection=inspections.get(file_path),
            )
            patches.append(patch)

        return {
            "status": "patch_proposal_only",
            "task": task,
            "change_type": change_type,
            "risk_level": risk_level,
            "requires_approval": True,
            "safe_to_apply_automatically": False,
            "patches": [asdict(p) for p in patches],
            "notes": [
                "No files were modified.",
                "This is a proposal-only patch plan.",
                "Human approval is required before any apply step.",
            ],
        }

    def _build_placeholder_patch(
        self,
        task: str,
        file_path: str,
        change_type: str,
        risk_level: str,
        inspection: Any = None,
    ) -> ProposedPatch:
        original = [
            f"# Existing file or directory: {file_path}",
            "# Jarvis inspected this target before modification.",
        ]

        proposed = [
            f"# Proposed safe update for: {file_path}",
            f"# Task: {task}",
            "# No automatic code changes generated yet.",
            "# Next phase will connect AI-generated diffs here.",
        ]

        diff = "\n".join(
            difflib.unified_diff(
                original,
                proposed,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                lineterm="",
            )
        )

        reason = "Initial safe patch proposal generated from planning and inspection context."

        return ProposedPatch(
            file_path=file_path,
            change_type=change_type,
            risk_level=risk_level,
            reason=reason,
            diff_preview=diff,
            requires_approval=True,
        )

    def _estimate_risk(self, task: str, files: List[str]) -> str:
        text = f"{task} {' '.join(files)}".lower()

        if any(keyword in text for keyword in self.DANGEROUS_KEYWORDS):
            return "high"

        if any(x in text for x in ["database", "migration", "db.py", "schema", "journal"]):
            return "medium"

        if any(x in text for x in ["template", "html", "css", "ui", "style", "screen", "page"]):
            return "low"

        return "medium"

    def _guess_change_type(self, task: str) -> str:
        text = task.lower()

        if any(x in text for x in ["ui", "screen", "template", "html", "css", "شكل", "شاشة"]):
            return "ui_update"

        if any(x in text for x in ["database", "migration", "table", "sqlite", "db"]):
            return "database_change"

        if any(x in text for x in ["test", "pytest", "اختبار"]):
            return "test_update"

        return "safe_modification"
