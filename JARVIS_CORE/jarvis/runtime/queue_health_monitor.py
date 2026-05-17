from pathlib import Path
from datetime import datetime, timezone
import json
import shutil

ROOT = Path(__file__).resolve().parents[3]
MEM = ROOT / "JARVIS_CORE" / "runtime_memory"
LOGS = ROOT / "JARVIS_CORE" / "runtime_logs"
BACKUPS = ROOT / "JARVIS_CORE" / "runtime_backups"

QUEUE = MEM / "command_queue.jsonl"
WORKER = MEM / "runtime_worker_state.json"
SUMMARY = MEM / "runtime_execution_summary.json"
HEALTH = MEM / "queue_health_state.json"
EVENTS = LOGS / "queue_health_events.jsonl"

VALID_STATES = {
    "queued",
    "validating",
    "running",
    "completed",
    "failed",
    "rejected",
    "failed_recoverable",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs():
    MEM.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    BACKUPS.mkdir(parents=True, exist_ok=True)


def log_event(event):
    ensure_dirs()
    event["timestamp"] = now()
    with EVENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def backup_file(path):
    if path.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = BACKUPS / f"{path.name}.{stamp}.bak"
        shutil.copy2(path, target)
        return str(target)
    return None


def read_json(path, default):
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        backup = backup_file(path)
        log_event({"level": "warning", "event": "json_corrupt", "file": str(path), "backup": backup})
        return default


def write_json(path, data):
    ensure_dirs()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_queue():
    ensure_dirs()
    if not QUEUE.exists():
        QUEUE.write_text("", encoding="utf-8")
        return []

    items = []
    bad_lines = 0

    with QUEUE.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                if not isinstance(item, dict):
                    bad_lines += 1
                    continue
                item.setdefault("status", "queued")
                if item["status"] not in VALID_STATES:
                    item["status"] = "failed_recoverable"
                    item["recovery_reason"] = "invalid_status"
                items.append(item)
            except Exception:
                bad_lines += 1

    if bad_lines:
        backup = backup_file(QUEUE)
        rewrite_queue(items)
        log_event({
            "level": "warning",
            "event": "queue_rebuilt",
            "bad_lines": bad_lines,
            "backup": backup,
        })

    return items


def rewrite_queue(items):
    ensure_dirs()
    with QUEUE.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def stabilize_queue():
    items = read_queue()

    seen = set()
    clean = []
    duplicates = 0

    for item in items:
        cid = item.get("command_id") or item.get("id")
        if not cid:
            cid = f"recovered-{len(clean)+1}-{datetime.now().timestamp()}"
            item["command_id"] = cid
            item["recovery_reason"] = "missing_command_id"

        if cid in seen:
            duplicates += 1
            continue

        seen.add(cid)
        clean.append(item)

    if duplicates:
        backup = backup_file(QUEUE)
        rewrite_queue(clean)
        log_event({
            "level": "warning",
            "event": "duplicates_removed",
            "duplicates": duplicates,
            "backup": backup,
        })

    worker = read_json(WORKER, {})
    if not isinstance(worker, dict):
        worker = {}

    if worker.get("status") in {"running", "locked"}:
        worker["status"] = "failed_recoverable"
        worker["recovery_reason"] = "worker_was_stuck_or_locked"
        worker["recovered_at"] = now()

    queued = [x for x in clean if x.get("status") == "queued"]
    running = [x for x in clean if x.get("status") == "running"]
    completed = [x for x in clean if x.get("status") == "completed"]
    failed = [x for x in clean if str(x.get("status", "")).startswith("failed")]

    summary = {
        "timestamp": now(),
        "queue_total": len(clean),
        "queued": len(queued),
        "running": len(running),
        "completed": len(completed),
        "failed": len(failed),
        "latest_task": clean[-1] if clean else None,
        "worker": worker,
        "health": "ok" if not running else "watching",
    }

    state = {
        "ok": True,
        "timestamp": now(),
        "queue_file": str(QUEUE),
        "items": len(clean),
        "duplicates_removed": duplicates,
        "worker_status": worker.get("status", "idle"),
        "summary": summary,
    }

    write_json(WORKER, worker)
    write_json(SUMMARY, summary)
    write_json(HEALTH, state)

    log_event({
        "level": "info",
        "event": "queue_health_check_completed",
        "items": len(clean),
        "queued": len(queued),
        "running": len(running),
        "completed": len(completed),
        "failed": len(failed),
    })

    return state


if __name__ == "__main__":
    print(json.dumps(stabilize_queue(), ensure_ascii=False, indent=2))
