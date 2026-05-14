
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

from jarvis.runtime.rollback_recovery_engine import create_runtime_checkpoint
from jarvis.runtime.staged_patch_generator import get_staged_patch_preview

ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ROOT.parent
MEMORY = ROOT / "runtime_memory"
MUTATION_STATE = MEMORY / "structured_patch_mutation_state.json"

APPROVAL_PHRASE = "APPROVE_STRUCTURED_MUTATION"

BOUNDED = True
DANGEROUS_AUTONOMOUS_APPLY = False

ALLOWED_TARGETS = {
    "templates/jarvis/mobile_control_center.html",
}

MANAGED_BLOCK_START = "<!-- JARVIS_STRUCTURED_MUTATION_START -->"
MANAGED_BLOCK_END = "<!-- JARVIS_STRUCTURED_MUTATION_END -->"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _safe_target(path_text):
    if path_text not in ALLOWED_TARGETS:
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
            timeout=25,
        )
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout[-3000:],
            "stderr": result.stderr[-3000:],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _build_managed_block(patch):
    preview = patch.get("patch_preview", [])

    lines = [
        MANAGED_BLOCK_START,
        "<!-- Runtime controlled structured mutation block. -->",
        f"<!-- updated_at={_now()} -->",
    ]

    for item in preview:
        lines.append(str(item))

    lines.append(MANAGED_BLOCK_END)

    return "\n".join(lines)


def _replace_or_append_managed_block(text, block):
    if MANAGED_BLOCK_START in text and MANAGED_BLOCK_END in text:
        before = text.split(MANAGED_BLOCK_START, 1)[0]
        after = text.split(MANAGED_BLOCK_END, 1)[1]
        return before + block + after

    if "</body>" in text:
        return text.replace("</body>", block + "\n</body>", 1)

    return text + "\n" + block + "\n"


def apply_structured_mutation(approval_phrase: str):
    patch = get_staged_patch_preview()

    state = {
        "timestamp": _now(),
        "runtime": "structured_patch_mutation",
        "bounded": BOUNDED,
        "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
        "approval_phrase_required": APPROVAL_PHRASE,
        "approval_phrase_received": approval_phrase,
        "project_mutation_attempted": False,
        "project_mutation_allowed": False,
        "autonomous_apply_allowed": False,
        "state": "blocked",
        "governance": {
            "human_approval_required": True,
            "allowed_targets_only": True,
            "managed_block_only": True,
            "checkpoint_before_mutation": True,
            "compile_after_mutation": True,
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
        state["reason"] = "target_not_allowed_or_missing"
        state["target_file"] = patch.get("target_file")
        _save_state(state)
        return state

    checkpoint = create_runtime_checkpoint()

    original = target.read_text(encoding="utf-8", errors="ignore")
    block = _build_managed_block(patch)
    updated = _replace_or_append_managed_block(original, block)

    target.write_text(updated, encoding="utf-8")

    compile_result = _compile_app()
    validation_ok = compile_result.get("ok") is True

    state.update({
        "project_mutation_attempted": True,
        "project_mutation_allowed": True,
        "state": "mutation_applied_validated" if validation_ok else "mutation_applied_validation_failed",
        "reason": "structured_managed_block_mutation_applied",
        "target_file": str(target),
        "checkpoint": checkpoint,
        "compile_result": compile_result,
        "validation_ok": validation_ok,
        "rollback_required": not validation_ok,
    })

    if not validation_ok:
        state["project_mutation_allowed"] = False

    _save_state(state)
    return state


def get_structured_mutation_state():
    if not MUTATION_STATE.exists():
        return {
            "runtime": "structured_patch_mutation",
            "state": "not_run",
            "bounded": BOUNDED,
            "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
            "project_mutation_allowed": False,
        }

    return json.loads(MUTATION_STATE.read_text(encoding="utf-8"))


def _save_state(state):
    MEMORY.mkdir(parents=True, exist_ok=True)
    MUTATION_STATE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
