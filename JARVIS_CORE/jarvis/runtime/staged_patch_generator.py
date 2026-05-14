
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
MEMORY = ROOT / "runtime_memory"
PATCH_FILE = MEMORY / "staged_patch_preview.json"

BOUNDED = True
DANGEROUS_AUTONOMOUS_APPLY = False


SAFE_PATCH_TEMPLATES = {
    "improve logging": {
        "target_file": "app.py",
        "patch_preview": [
            "# add structured runtime logging",
            "# improve bounded diagnostics visibility",
        ],
    },

    "improve hud": {
        "target_file": "templates/jarvis/mobile_control_center.html",
        "patch_preview": [
            "<!-- improve responsive runtime layout -->",
            "<!-- enhance governance visibility -->",
        ],
    },

    "improve runtime": {
        "target_file": "JARVIS_CORE/jarvis/runtime/runtime_engine.py",
        "patch_preview": [
            "# improve runtime orchestration",
            "# add safer staged monitoring",
        ],
    },
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _select_patch_template(message: str):
    text = (message or "").lower()

    for key, value in SAFE_PATCH_TEMPLATES.items():
        if key in text:
            return value

    return {
        "target_file": "unknown",
        "patch_preview": [
            "# no approved patch template matched",
        ],
    }


def generate_staged_patch(message: str):

    template = _select_patch_template(message)

    report = {
        "patch_id": str(uuid.uuid4()),
        "timestamp": _now(),
        "runtime": "staged_patch_generator",
        "request": message,
        "target_file": template["target_file"],
        "patch_preview": template["patch_preview"],
        "patch_state": "preview_only",
        "apply_allowed": False,
        "bounded": BOUNDED,
        "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
        "governance": {
            "human_approval_required": True,
            "sandbox_apply_required": True,
            "compile_required_after_apply": True,
            "rollback_required_on_failure": True,
            "direct_mutation_blocked": True,
        },
    }

    MEMORY.mkdir(parents=True, exist_ok=True)

    PATCH_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return report


def get_staged_patch_preview():

    if not PATCH_FILE.exists():
        return {
            "runtime": "staged_patch_generator",
            "state": "no_patch_generated",
            "bounded": BOUNDED,
            "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
        }

    return json.loads(
        PATCH_FILE.read_text(encoding="utf-8")
    )
