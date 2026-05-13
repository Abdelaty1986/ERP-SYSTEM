from pathlib import Path
import json
from datetime import datetime

from JARVIS_CORE.jarvis.architecture.safe_execution_queue_engine import SafeExecutionQueueEngine


class HumanApprovedApplyEngine:
    def __init__(self, project_root="."):
        self.project_root = Path(project_root)

        self.memory_dir = self.project_root / "JARVIS_CORE/runtime_memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.apply_file = self.memory_dir / "human_approved_apply.json"

    def prepare_apply(self, objective="safe_architecture_refactor"):
        queue = SafeExecutionQueueEngine(self.project_root).build_queue(objective)

        summary = queue.get("summary", {})
        queued = queue.get("queue", [])

        apply_id = f"apply-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        staged = []

        for item in queued:
            staged.append({
                "phase": item["phase"],
                "task": item["task"],
                "execution_state": "awaiting_human_approval",
                "rollback_checkpoint": item["rollback_checkpoint"],
                "execution_locked": True,
                "bounded": True,
                "autonomous_apply": False
            })

        payload = {
            "bounded": True,
            "mode": "human_approved_apply",
            "autonomous_apply": False,

            "summary": {
                "apply_id": apply_id,
                "objective": objective,
                "apply_state": "awaiting_human_approval",
                "staged_steps": len(staged),
                "execution_allowed": False,
                "rollback_ready": summary.get("rollback_ready", False)
            },

            "staged_execution": staged,

            "governance": {
                "human_approval_required": True,
                "rollback_required": True,
                "execution_locking": True,
                "recovery_tracking": True,
                "journal_mode": "bounded_execution_journal"
            },

            "notes": [
                "Human approved apply prepares staged execution only.",
                "No code changes are executed automatically.",
                "All execution remains human-governed and reversible."
            ]
        }

        self.apply_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return payload
