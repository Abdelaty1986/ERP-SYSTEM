
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

from jarvis.runtime.rollback_recovery_engine import create_runtime_checkpoint
from jarvis.runtime.staged_patch_generator import get_staged_patch_preview

ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ROOT.parent
MEMORY = ROOT / "runtime_memory"
APPLY_STATE = MEMORY / "approved_project_apply_state.json"

APPROVAL_PHRASE = "APPROVE_PROJECT_APPLY"

BOUNDED = True
DANGEROUS_AUTONOMOUS_APPLY = False


def _now():
    return datetime.now(timezone.utc).isoformat()


def _safe_target(path_text):
    if not path_text or path_text == "unknown":
        return None

    target = (PROJECT_ROOT / path_text).resolve()
    project = PROJECT_ROOT.resolve()

    if project not in target.parents and target != project:
        return None

    if not target.exists() or not target.is_file():
        return None

    return target


def _compile_app():
    try:
        result = subprocess.run(
            ["python", "-m", "py_compile", "app.py"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=20,
        )
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout[-3000:],
            "stderr": result.stderr[-3000:],
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }


def approved_project_apply(approval_phrase: str):
    patch = get_staged_patch_preview()

    state = {
        "timestamp": _now(),
        "runtime": "approved_project_apply_gate",
        "bounded": BOUNDED,
        "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
        "approval_phrase_required": APPROVAL_PHRASE,
        "approval_phrase_received": approval_phrase,
        "project_apply_attempted": False,
        "project_apply_allowed": False,
        "autonomous_apply_allowed": False,
        "state": "blocked",
        "governance": {
            "human_approval_required": True,
            "checkpoint_before_apply_required": True,
            "compile_after_apply_required": True,
            "rollback_on_failure_required": True,
            "no_git_commit": True,
            "no_git_push": True,
        },
    }

    if approval_phrase != APPROVAL_PHRASE:
        state["reason"] = "missing_or_invalid_human_approval_phrase"
        _save_state(state)
        return state

    target = _safe_target(patch.get("target_file"))

    if not target:
        state["reason"] = "unsafe_or_missing_target"
        _save_state(state)
        return state

    checkpoint = create_runtime_checkpoint()

    marker_lines = patch.get("patch_preview", [])
    suffix = target.suffix.lower()

    if suffix in [".html", ".htm"]:
        block = [
            "",
            "<!-- JARVIS APPROVED PROJECT APPLY -->",
            "<!-- Human approved bounded apply. -->",
        ] + [str(x) for x in marker_lines]
    else:
        block = [
            "",
            "# --- JARVIS APPROVED PROJECT APPLY ---",
            "# Human approved bounded apply.",
        ] + [str(x) for x in marker_lines]

    with target.open("a", encoding="utf-8", errors="ignore") as f:
        f.write("\n".join(block) + "\n")

    compile_result = _compile_app()

    state.update({
        "project_apply_attempted": True,
        "project_apply_allowed": True,
        "state": "applied_pending_validation",
        "reason": "human_approval_phrase_matched",
        "target_file": str(target),
        "checkpoint": checkpoint,
        "compile_result": compile_result,
        "validation_ok": compile_result.get("ok") is True,
    })

    if not compile_result.get("ok"):
        state["state"] = "applied_validation_failed_manual_rollback_required"
        state["project_apply_allowed"] = False

    _save_state(state)
    return state


def _save_state(state):
    MEMORY.mkdir(parents=True, exist_ok=True)
    APPLY_STATE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_approved_project_apply_state():
    if not APPLY_STATE.exists():
        return {
            "runtime": "approved_project_apply_gate",
            "state": "not_run",
            "bounded": BOUNDED,
            "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
            "project_apply_allowed": False,
        }

    return json.loads(APPLY_STATE.read_text(encoding="utf-8"))
