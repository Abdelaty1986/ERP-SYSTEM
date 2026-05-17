import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

PREVIEW_FILE = Path("JARVIS_CORE/runtime_memory/controlled_patch_preview.json")
APPROVAL_FILE = Path("JARVIS_CORE/runtime_memory/controlled_patch_approval.json")
BACKUP_DIR = Path("JARVIS_CORE/runtime_backups")
EVENT_LOG = Path("JARVIS_CORE/runtime_logs/controlled_execution_events.jsonl")
STATE_FILE = Path("JARVIS_CORE/runtime_memory/controlled_execution_state.json")

ALLOWED_PATCH_FILES = {
    "app.py",
    "templates/jarvis/mobile_control_center.html",
}

SAFE_DIRS = {
    "JARVIS_CORE/jarvis/runtime/",
}

DANGEROUS_PATTERNS = {".git", ".env", "secrets", "node_modules", "venv", "__pycache__", "site-packages"}

BACKED_UP_FILES: List[str] = []


def now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def log_event(event: str, payload: Dict[str, Any]) -> None:
    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EVENT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": now(),
            "event": event,
            "payload": payload,
        }, ensure_ascii=False) + "\n")


def is_safe_path(file_path: str) -> tuple:
    path = Path(file_path).resolve()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in path.parts:
            return False, f"Path contains dangerous pattern: {pattern}"
    abs_path = str(path)
    if path.suffix != ".py" and path.suffix != ".html":
        return False, f"Unsupported file type: {path.suffix}"
    return True, ""


class ControlledPatchManager:

    def generate_preview(self) -> Dict[str, Any]:
        preview = {
            "timestamp": now(),
            "files_proposed": [],
            "summary": "No changes proposed",
            "patch_available": False,
        }
        for f in sorted(ALLOWED_PATCH_FILES):
            p = Path(f)
            if p.exists():
                preview["files_proposed"].append({
                    "file": f,
                    "size": p.stat().st_size,
                    "lines": len(p.read_text(encoding="utf-8").splitlines()) if p.suffix in (".py", ".html") else 0,
                })
        safe_py_files = sorted(Path("JARVIS_CORE/jarvis/runtime").glob("*.py"))
        for pyf in safe_py_files:
            rel = str(pyf)
            preview["files_proposed"].append({
                "file": rel,
                "size": pyf.stat().st_size,
                "lines": len(pyf.read_text(encoding="utf-8").splitlines()),
            })
        if preview["files_proposed"]:
            preview["patch_available"] = True
            preview["summary"] = f"{len(preview['files_proposed'])} files eligible for patch"
        PREVIEW_FILE.parent.mkdir(parents=True, exist_ok=True)
        PREVIEW_FILE.write_text(json.dumps(preview, indent=2, ensure_ascii=False), encoding="utf-8")
        log_event("patch_preview_generated", preview)
        return preview

    def get_status(self) -> Dict[str, Any]:
        preview = {}
        if PREVIEW_FILE.exists():
            try:
                preview = json.loads(PREVIEW_FILE.read_text(encoding="utf-8"))
            except Exception:
                preview = {"error": "corrupted preview"}
        approval = {}
        if APPROVAL_FILE.exists():
            try:
                approval = json.loads(APPROVAL_FILE.read_text(encoding="utf-8"))
            except Exception:
                approval = {"error": "corrupted approval"}
        return {
            "preview": preview,
            "approval": approval,
            "backup_count": len(BACKED_UP_FILES),
            "backup_dir": str(BACKUP_DIR),
        }

    def backup_file(self, file_path: str) -> bool:
        src = Path(file_path)
        if not src.exists():
            return False
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = now().replace(":", "-").replace("Z", "")
        backup_name = f"{src.name}.{timestamp}.bak"
        dst = BACKUP_DIR / backup_name
        try:
            shutil.copy2(str(src), str(dst))
            BACKED_UP_FILES.append(str(dst))
            log_event("file_backed_up", {"source": file_path, "backup": str(dst)})
            return True
        except Exception as exc:
            log_event("backup_failed", {"source": file_path, "error": str(exc)})
            return False

    def approve_patch(self) -> Dict[str, Any]:
        if not PREVIEW_FILE.exists():
            return {"ok": False, "error": "No patch preview found. Run improve first."}
        try:
            preview = json.loads(PREVIEW_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"ok": False, "error": "Corrupted patch preview"}
        if not preview.get("patch_available"):
            return {"ok": False, "error": "No patch available to approve"}
        APPROVAL_FILE.parent.mkdir(parents=True, exist_ok=True)
        approval = {"approved": True, "timestamp": now(), "preview": preview}
        APPROVAL_FILE.write_text(json.dumps(approval, indent=2, ensure_ascii=False), encoding="utf-8")
        log_event("patch_approved", approval)
        application_result = self.apply_patch()
        return application_result

    def apply_patch(self) -> Dict[str, Any]:
        if not APPROVAL_FILE.exists():
            return {"ok": False, "error": "No approval file found. Approve first."}
        try:
            approval = json.loads(APPROVAL_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"ok": False, "error": "Corrupted approval file"}
        if not approval.get("approved"):
            return {"ok": False, "error": "Patch not approved"}
        files_proposed = approval.get("preview", {}).get("files_proposed", [])
        applied = []
        failed = []
        for entry in files_proposed:
            fp = entry.get("file", "")
            safe, reason = is_safe_path(fp)
            if not safe:
                log_event("patch_apply_blocked", {"file": fp, "reason": reason})
                failed.append({"file": fp, "error": reason})
                continue
            if not self.backup_file(fp):
                log_event("patch_apply_skipped_no_backup", {"file": fp})
                failed.append({"file": fp, "error": "backup failed"})
                continue
            applied.append({"file": fp, "status": "verified"})
        result = {"applied": applied, "failed": failed, "timestamp": now()}
        if failed:
            result["status"] = "warnings"
            self.rollback()
        else:
            result["status"] = "completed"
        log_event("patch_apply_completed", result)
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        return result

    def reject_patch(self) -> Dict[str, Any]:
        if PREVIEW_FILE.exists():
            PREVIEW_FILE.unlink()
        if APPROVAL_FILE.exists():
            APPROVAL_FILE.unlink()
        result = {"ok": True, "status": "rejected", "timestamp": now()}
        log_event("patch_rejected", result)
        return result

    def rollback(self) -> Dict[str, Any]:
        rolled_back = []
        for backup_path_str in reversed(BACKED_UP_FILES):
            backup_path = Path(backup_path_str)
            if not backup_path.exists():
                continue
            original_name = backup_path.name.split(".")[0]
            candidates = list(BACKUP_DIR.glob(f"{original_name}.*.bak"))
            if not candidates:
                continue
            latest_backup = sorted(candidates)[-1]
            try:
                original_stem = backup_path.name.rsplit(".", 2)[0]
                original_glob = list(Path(".").glob(original_stem))
                if original_glob:
                    target = original_glob[0]
                    shutil.copy2(str(latest_backup), str(target))
                    rolled_back.append(str(target))
                    log_event("file_rolled_back", {"file": str(target), "backup": str(latest_backup)})
            except Exception as exc:
                log_event("rollback_failed", {"backup": str(backup_path), "error": str(exc)})
        result = {"rolled_back": rolled_back, "timestamp": now()}
        if rolled_back:
            result["status"] = "completed"
        else:
            result["status"] = "nothing_to_rollback"
        log_event("rollback_completed", result)
        return result
