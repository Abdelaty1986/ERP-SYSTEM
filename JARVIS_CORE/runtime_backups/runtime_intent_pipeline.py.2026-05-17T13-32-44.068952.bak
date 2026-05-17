
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]

RUNTIME_MEMORY = ROOT / "runtime_memory"
INTENT_QUEUE = RUNTIME_MEMORY / "runtime_intent_queue.json"

BOUNDED = True
DANGEROUS_AUTONOMOUS_APPLY = False


SAFE_INTENTS = {
    "report": ["report", "status", "summary"],
    "analysis": ["analyze", "inspect", "review"],
    "testing": ["test", "check", "verify"],
    "improvement": ["improve", "optimize", "enhance"],
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load_queue():
    if not INTENT_QUEUE.exists():
        return []

    try:
        return json.loads(
            INTENT_QUEUE.read_text(encoding="utf-8")
        )
    except Exception:
        return []


def _save_queue(queue):
    RUNTIME_MEMORY.mkdir(parents=True, exist_ok=True)

    INTENT_QUEUE.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def classify_intent(message: str):
    text = (message or "").lower()

    for intent, keywords in SAFE_INTENTS.items():
        for keyword in keywords:
            if keyword in text:
                return intent

    return "unknown"


def create_intent_entry(message: str):
    intent = classify_intent(message)

    entry = {
        "intent_id": str(uuid.uuid4()),
        "timestamp": _now(),
        "message": message,
        "classified_intent": intent,
        "execution_mode": "simulation_only",
        "execution_allowed": False,
        "bounded": BOUNDED,
        "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
        "governance": {
            "rollback_safe": True,
            "staged_progression": True,
            "human_approval_required": True,
            "runtime_monitored": True,
        }
    }

    queue = _load_queue()
    queue.append(entry)
    _save_queue(queue)

    return entry


def get_runtime_intent_queue():
    return {
        "runtime": "runtime_intent_pipeline",
        "bounded": BOUNDED,
        "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
        "queue_size": len(_load_queue()),
        "queue": _load_queue()[-10:]
    }
