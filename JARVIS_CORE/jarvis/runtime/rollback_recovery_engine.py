
import json
import shutil
import uuid
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ROOT.parent

MEMORY = ROOT / "runtime_memory"
ROLLBACK_DIR = ROOT / "runtime_rollback"
ROLLBACK_LOG = MEMORY / "rollback_recovery_state.json"

BOUNDED = True
DANGEROUS_AUTONOMOUS_APPLY = False


def _now():
    return datetime.now(timezone.utc).isoformat()


def create_runtime_checkpoint():

    checkpoint_id = str(uuid.uuid4())

    checkpoint_dir = ROLLBACK_DIR / checkpoint_id
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    tracked_files = [
        PROJECT_ROOT / "app.py",
        PROJECT_ROOT / "templates/jarvis/mobile_control_center.html",
    ]

    copied = []

    for file_path in tracked_files:

        if not file_path.exists():
            continue

        target = checkpoint_dir / file_path.name

        shutil.copy2(file_path, target)

        copied.append(str(target))

    report = {
        "timestamp": _now(),
        "runtime": "rollback_recovery_engine",
        "checkpoint_id": checkpoint_id,
        "checkpoint_state": "created",
        "bounded": BOUNDED,
        "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
        "rollback_ready": True,
        "tracked_files": copied,
        "project_restore_allowed": False,
        "governance": {
            "human_approval_required_for_restore": True,
            "automatic_destructive_restore_blocked": True,
            "safe_checkpointing_enabled": True,
        },
    }

    MEMORY.mkdir(parents=True, exist_ok=True)

    ROLLBACK_LOG.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return report


def get_rollback_state():

    if not ROLLBACK_LOG.exists():
        return {
            "runtime": "rollback_recovery_engine",
            "state": "no_checkpoint",
            "bounded": BOUNDED,
            "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
        }

    return json.loads(
        ROLLBACK_LOG.read_text(encoding="utf-8")
    )
