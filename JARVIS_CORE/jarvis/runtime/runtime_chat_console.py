import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "runtime_logs"
CHAT_LOG = LOG_DIR / "runtime_chat_console.jsonl"
EVENT_LOG = LOG_DIR / "runtime_events.jsonl"

BOUNDED = True
DANGEROUS_AUTONOMOUS_APPLY = False


def _now():
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path, payload):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def submit_chat_message(message, source="mobile_hud"):
    message = (message or "").strip()
    if not message:
        return {
            "accepted": False,
            "reason": "empty_message",
            "bounded": BOUNDED,
            "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
        }

    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": _now(),
        "runtime": "runtime_chat_console",
        "source": source,
        "message": message,
        "state": "recorded_only",
        "execution_allowed": False,
        "bounded": BOUNDED,
        "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
        "governance": {
            "rollback_safe": True,
            "staged_progression": True,
            "monitored_runtime": True,
            "no_dangerous_autonomous_apply": True,
        },
    }

    event = {
        "timestamp": entry["timestamp"],
        "event": "runtime_chat_console_message_recorded",
        "runtime": "runtime_chat_console",
        "message_id": entry["id"],
        "state": "monitored",
        "bounded": BOUNDED,
        "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
    }

    _append_jsonl(CHAT_LOG, entry)
    _append_jsonl(EVENT_LOG, event)

    return {"accepted": True, "entry": entry}


def get_chat_console_state(limit=10):
    items = []
    if CHAT_LOG.exists():
        lines = CHAT_LOG.read_text(encoding="utf-8").splitlines()[-limit:]
        for line in lines:
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return {
        "runtime": "runtime_chat_console",
        "bounded": BOUNDED,
        "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
        "state": "active",
        "messages": items,
    }
