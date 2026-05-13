from pathlib import Path
import json
from datetime import datetime

from JARVIS_CORE.jarvis.architecture.controlled_apply_decision_engine import ControlledApplyDecisionEngine


class RollbackCheckpointEngine:
    def __init__(self, project_root="."):
        self.project_root = Path(project_root)

        self.memory_dir = self.project_root / "JARVIS_CORE/runtime_memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.rollback_file = self.memory_dir / "rollback_checkpoint_memory.json"

    def build_checkpoint(self, objective="safe_architecture_refactor"):
        decision = ControlledApplyDecisionEngine(self.project_root).decide(objective)

        summary = decision.get("summary", {})

        checkpoint_id = f"checkpoint-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        payload = {
            "bounded": True,
            "mode": "rollback_checkpoint_runtime",
            "autonomous_apply": False,

            "summary": {
                "checkpoint_id": checkpoint_id,
                "objective": objective,
                "checkpoint_state": "ready",
                "rollback_ready": summary.get("rollback_ready", False),
                "execution_allowed": False,
                "human_approval_required": True
            },

            "recovery_plan": {
                "strategy": "bounded_restore_sequence",
                "validation_required": True,

                "recovery_steps": [
                    "Restore modified files",
                    "Re-run py_compile validation",
                    "Re-run endpoint smoke tests",
                    "Verify runtime integrity",
                    "Confirm bounded runtime state"
                ]
            },

            "checkpoint_lineage": {
                "source_runtime": "controlled_apply_decision",
                "linked_objective": objective,
                "continuity_state": "preserved",
                "recovery_graph_state": "stable"
            },

            "notes": [
                "Rollback checkpoints prepare recovery states.",
                "No restore execution is performed automatically.",
                "Recovery remains human-governed."
            ]
        }

        self.rollback_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return payload
