
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

from jarvis.runtime.staged_patch_generator import generate_staged_patch, get_staged_patch_preview
from jarvis.runtime.sandbox_patch_apply import sandbox_apply_latest_patch, get_sandbox_apply_result
from jarvis.runtime.rollback_recovery_engine import create_runtime_checkpoint, get_rollback_state
from jarvis.runtime.runtime_governance_decision import create_governance_decision

ROOT = Path(__file__).resolve().parents[2]
MEMORY = ROOT / "runtime_memory"
ENGINEERING_STATE = MEMORY / "human_approved_engineering_state.json"

BOUNDED = True
DANGEROUS_AUTONOMOUS_APPLY = False


def _now():
    return datetime.now(timezone.utc).isoformat()


def prepare_human_approved_engineering(message: str):
    governance = create_governance_decision(message)
    patch = generate_staged_patch(message)
    sandbox = sandbox_apply_latest_patch()
    checkpoint = create_runtime_checkpoint()

    ready = (
        governance.get("execution_allowed") is False
        and patch.get("apply_allowed") is False
        and sandbox.get("project_mutation_allowed") is False
        and checkpoint.get("rollback_ready") is True
    )

    state = {
        "session_id": str(uuid.uuid4()),
        "timestamp": _now(),
        "runtime": "human_approved_engineering",
        "request": message,
        "bounded": BOUNDED,
        "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
        "engineering_state": "prepared_awaiting_human_approval",
        "ready_for_human_review": ready,
        "project_apply_allowed": False,
        "autonomous_apply_allowed": False,
        "requires_explicit_human_approval": True,
        "governance_decision": governance,
        "staged_patch": get_staged_patch_preview(),
        "sandbox_result": get_sandbox_apply_result(),
        "rollback_state": get_rollback_state(),
        "approval_contract": {
            "can_apply_to_project_now": False,
            "approval_phrase_required": "APPROVE_PROJECT_APPLY",
            "must_compile_after_apply": True,
            "must_runtime_test_after_apply": True,
            "must_rollback_on_failure": True,
            "can_commit_without_human": False,
            "can_push_without_human": False,
        },
    }

    MEMORY.mkdir(parents=True, exist_ok=True)
    ENGINEERING_STATE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return state


def get_human_approved_engineering_state():
    if not ENGINEERING_STATE.exists():
        return {
            "runtime": "human_approved_engineering",
            "engineering_state": "not_prepared",
            "bounded": BOUNDED,
            "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
            "project_apply_allowed": False,
        }

    return json.loads(
        ENGINEERING_STATE.read_text(encoding="utf-8")
    )
