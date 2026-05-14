
import json
import shutil
import uuid
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ROOT.parent
MEMORY = ROOT / "runtime_memory"
SANDBOX_DIR = ROOT / "runtime_sandbox"
PATCH_FILE = MEMORY / "staged_patch_preview.json"
SANDBOX_RESULT = MEMORY / "sandbox_patch_apply_result.json"

BOUNDED = True
DANGEROUS_AUTONOMOUS_APPLY = False


def _now():
    return datetime.now(timezone.utc).isoformat()


def _safe_target(path_text):
    if not path_text or path_text == "unknown":
        return None

    target = (PROJECT_ROOT / path_text).resolve()

    if PROJECT_ROOT.resolve() not in target.parents and target != PROJECT_ROOT.resolve():
        return None

    if not target.exists() or not target.is_file():
        return None

    return target


def sandbox_apply_latest_patch():
    if not PATCH_FILE.exists():
        return {
            "runtime": "sandbox_patch_apply",
            "state": "no_patch_preview_found",
            "bounded": BOUNDED,
            "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
            "project_mutation_allowed": False,
        }

    patch = json.loads(PATCH_FILE.read_text(encoding="utf-8"))
    target = _safe_target(patch.get("target_file"))

    result = {
        "sandbox_id": str(uuid.uuid4()),
        "timestamp": _now(),
        "runtime": "sandbox_patch_apply",
        "source_patch_id": patch.get("patch_id"),
        "target_file": patch.get("target_file"),
        "bounded": BOUNDED,
        "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
        "project_mutation_allowed": False,
        "apply_scope": "sandbox_only",
        "execution_allowed_on_project": False,
        "governance": {
            "human_approval_required": True,
            "direct_project_apply_blocked": True,
            "rollback_required_on_failure": True,
            "compile_required_before_project_apply": True,
        },
    }

    if not target:
        result.update({
            "state": "blocked",
            "reason": "unsafe_or_missing_target",
            "sandbox_file": None,
            "ok": False,
        })
    else:
        SANDBOX_DIR.mkdir(parents=True, exist_ok=True)

        sandbox_file = SANDBOX_DIR / target.name
        shutil.copy2(target, sandbox_file)

        marker = [
            "",
            "# --- JARVIS SANDBOX PATCH PREVIEW ---",
            "# This change is sandbox-only and was not applied to project files.",
        ]

        if target.suffix.lower() in [".html", ".htm"]:
            marker = [
                "",
                "<!-- JARVIS SANDBOX PATCH PREVIEW -->",
                "<!-- This change is sandbox-only and was not applied to project files. -->",
            ]

        with sandbox_file.open("a", encoding="utf-8", errors="ignore") as f:
            f.write("\n".join(marker) + "\n")
            for line in patch.get("patch_preview", []):
                f.write(str(line) + "\n")

        result.update({
            "state": "sandbox_applied",
            "reason": "patch_preview_applied_to_sandbox_copy_only",
            "sandbox_file": str(sandbox_file),
            "ok": True,
        })

    MEMORY.mkdir(parents=True, exist_ok=True)
    SANDBOX_RESULT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return result


def get_sandbox_apply_result():
    if not SANDBOX_RESULT.exists():
        return {
            "runtime": "sandbox_patch_apply",
            "state": "not_run",
            "bounded": BOUNDED,
            "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
            "project_mutation_allowed": False,
        }

    return json.loads(
        SANDBOX_RESULT.read_text(encoding="utf-8")
    )
