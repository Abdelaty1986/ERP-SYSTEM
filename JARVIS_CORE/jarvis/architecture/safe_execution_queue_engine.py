from pathlib import Path
import json
from datetime import datetime

from JARVIS_CORE.jarvis.architecture.rollback_checkpoint_engine import RollbackCheckpointEngine


class SafeExecutionQueueEngine:
    def __init__(self, project_root="."):
        self.project_root = Path(project_root)
        self.memory_dir = self.project_root / "JARVIS_CORE/runtime_memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.queue_file = self.memory_dir / "safe_execution_queue.json"

    def build_queue(self, objective="safe_architecture_refactor"):
        checkpoint = RollbackCheckpointEngine(self.project_root).build_checkpoint(objective)
        checkpoint_summary = checkpoint.get("summary", {})

        execution_id = f"exec-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        phases = [
            ("planning", "Generate bounded execution strategy"),
            ("reflection", "Validate execution coherence"),
            ("arbitration", "Rank execution decisions"),
            ("learning", "Record bounded learning signals"),
            ("failure_guard", "Monitor execution drift")
        ]

        queue = []

        for index, (phase, task) in enumerate(phases, start=1):
            queue.append({
                "step": index,
                "phase": phase,
                "task": task,
                "status": "queued",
                "execution_window": "bounded",
                "rollback_checkpoint": checkpoint_summary.get("checkpoint_id"),
                "human_approval_required": True,
                "execution_locked": True,
                "autonomous_apply": False,
                "bounded": True
            })

        payload = {
            "bounded": True,
            "mode": "safe_execution_queue",
            "autonomous_apply": False,
            "summary": {
                "execution_id": execution_id,
                "objective": objective,
                "queue_state": "ready_for_human_governance",
                "queued_steps": len(queue),
                "rollback_ready": checkpoint_summary.get("rollback_ready", False),
                "execution_allowed": False
            },
            "queue": queue,
            "governance": {
                "approval_required": True,
                "execution_locking": True,
                "retry_policy": "human_review_only",
                "recovery_mode": "checkpoint_restore"
            },
            "notes": [
                "Safe execution queue prepares governed execution ordering.",
                "No queued task is executed automatically.",
                "Execution remains human-controlled."
            ]
        }

        self.queue_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return payload
