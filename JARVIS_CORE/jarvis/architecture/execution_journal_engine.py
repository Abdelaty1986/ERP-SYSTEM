from pathlib import Path
import json
from datetime import datetime

from JARVIS_CORE.jarvis.architecture.human_approved_apply_engine import HumanApprovedApplyEngine


class ExecutionJournalEngine:
    def __init__(self, project_root="."):
        self.project_root = Path(project_root)

        self.memory_dir = self.project_root / "JARVIS_CORE/runtime_memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.journal_file = self.memory_dir / "execution_journal.json"

    def build_journal(self, objective="safe_architecture_refactor"):
        apply_runtime = HumanApprovedApplyEngine(
            self.project_root
        ).prepare_apply(objective)

        summary = apply_runtime.get("summary", {})
        staged = apply_runtime.get("staged_execution", [])

        journal_id = f"journal-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        journal_entries = []

        for index, item in enumerate(staged, start=1):
            journal_entries.append({
                "entry_id": f"{journal_id}-step-{index}",
                "phase": item["phase"],
                "task": item["task"],
                "execution_state": item["execution_state"],
                "rollback_checkpoint": item["rollback_checkpoint"],
                "journal_state": "recorded",
                "bounded": True,
                "autonomous_apply": False
            })

        payload = {
            "bounded": True,
            "mode": "execution_journal_runtime",
            "autonomous_apply": False,

            "summary": {
                "journal_id": journal_id,
                "objective": objective,
                "entries_recorded": len(journal_entries),
                "lineage_state": "persistent_execution_memory",
                "execution_allowed": False,
                "rollback_ready": summary.get("rollback_ready", False)
            },

            "journal_entries": journal_entries,

            "lineage": {
                "source_runtime": "human_approved_apply",
                "trace_mode": "bounded_execution_trace",
                "recovery_trace_enabled": True,
                "audit_state": "persistent",
                "continuity_state": "stable"
            },

            "notes": [
                "Execution journal records governed runtime execution lineage.",
                "No execution is performed automatically.",
                "All runtime operations remain bounded and human-controlled."
            ]
        }

        self.journal_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return payload
