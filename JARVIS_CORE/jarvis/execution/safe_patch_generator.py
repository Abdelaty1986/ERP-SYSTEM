from dataclasses import dataclass, asdict
from typing import List, Dict, Any
from pathlib import Path
import difflib

from jarvis.execution.real_diff_proposal_builder import RealDiffProposalBuilder
from jarvis.execution.target_resolver import TargetResolver


@dataclass
class ProposedPatch:
    file_path: str
    change_type: str
    risk_level: str
    reason: str
    diff_preview: str
    proposed_content: str | None = None
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
        self.real_diff_builder = RealDiffProposalBuilder()
        self.target_resolver = TargetResolver(project_root)

    def generate_patch_plan(
        self,
        task: str,
        expected_files: List[str],
        inspections: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        inspections = inspections or {}

        if isinstance(inspections, list):
            inspections = {
                item.get("file"): item
                for item in inspections
                if isinstance(item, dict) and item.get("file")
            }

        risk_level = self._estimate_risk(task, expected_files)
        change_type = self._guess_change_type(task)

        resolution = self.target_resolver.resolve_targets(
            expected_files
        )

        resolved_targets = resolution.get(
            "resolved_targets",
            []
        )

        patches: List[ProposedPatch] = []

        for file_path in resolved_targets:
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
            "target_resolution": resolution,
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
        real_diff = None

        if file_path and not file_path.endswith("/"):
            real_diff = self.real_diff_builder.build_safe_comment_diff(
                file_path=file_path,
                task=task,
            )

        if real_diff and real_diff.get("can_use"):
            reason = (
                "Real safe unified diff proposal generated "
                "without modifying source files."
            )

            return ProposedPatch(
                file_path=file_path,
                change_type=real_diff.get("change_type", change_type),
                risk_level=real_diff.get("risk_level", risk_level),
                reason=reason,
                diff_preview=real_diff.get("diff_preview", ""),
                proposed_content=real_diff.get("proposed_content"),
                requires_approval=True,
            )

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

        reason = "Fallback placeholder proposal generated because real diff was not available."

        return ProposedPatch(
            file_path=file_path,
            change_type=change_type,
            risk_level=risk_level,
            reason=reason,
            diff_preview=diff,
            proposed_content=None,
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
