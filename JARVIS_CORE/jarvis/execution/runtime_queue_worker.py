from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from jarvis.execution.runtime_worker_state import RuntimeWorkerState


ROOT = Path("JARVIS_CORE")
QUEUE_FILE = ROOT / "runtime_logs" / "runtime_command_queue.jsonl"
EVENT_LOG = ROOT / "runtime_logs" / "runtime_events.jsonl"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def log_event(event: str, payload: Dict[str, Any]) -> None:
    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EVENT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": now(),
            "event": event,
            "payload": payload,
        }, ensure_ascii=False) + "\n")


@dataclass
class QueueItem:
    id: str
    command: str
    status: str = "queued"
    reason: str = ""
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QueueItem":
        return cls(
            id=str(data.get("id") or data.get("command_id") or uuid.uuid4().hex[:12]),
            command=str(data.get("command") or data.get("type") or "unknown"),
            status=str(data.get("status") or "queued"),
            reason=str(data.get("reason") or ""),
            created_at=str(data.get("created_at") or data.get("timestamp") or now()),
            updated_at=str(data.get("updated_at") or now()),
        )


class RuntimeQueueWorker:
    """
    Safe queue worker stage 1:
    - reads persistent command queue
    - validates known commands only
    - updates lifecycle states
    - logs lifecycle
    - DOES NOT execute shell
    - DOES NOT apply patches
    """

    ALLOWED_COMMANDS = {
        "system_review",
        "run_tests",
        "scan_errors",
        "improve",
        "report",
    }

    def __init__(self, queue_file: Path = QUEUE_FILE):
        self.queue_file = queue_file

    def read_queue(self) -> List[QueueItem]:
        if not self.queue_file.exists():
            return []

        items: List[QueueItem] = []
        for line in self.queue_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(QueueItem.from_dict(json.loads(line)))
            except Exception as exc:
                log_event("runtime_queue_worker_bad_line", {"error": str(exc), "line": line})
        return items

    def write_queue(self, items: List[QueueItem]) -> None:
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        with self.queue_file.open("w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")

    def validate(self, item: QueueItem) -> bool:
        return item.command in self.ALLOWED_COMMANDS

    def process_once(self) -> Dict[str, Any]:
        items = self.read_queue()

        target = next((i for i in items if i.status == "queued"), None)
        if not target:
            return {"processed": False, "reason": "no queued commands"}

        RuntimeWorkerState.write(
            worker_status="running",
            last_command=target.command,
            last_result="started"
        )

        log_event("runtime_queue_worker_started", {"id": target.id, "command": target.command})

        target.status = "validating"
        target.updated_at = now()
        self.write_queue(items)

        if not self.validate(target):
            target.status = "blocked"
            target.reason = "command not allowed by RuntimeQueueWorker"
            target.updated_at = now()
            self.write_queue(items)
            log_event("runtime_queue_worker_blocked", asdict(target))
            return {"processed": True, "status": "blocked", "item": asdict(target)}

        target.status = "running"
        target.reason = "safe simulation lifecycle only - no direct execution"
        target.updated_at = now()
        self.write_queue(items)
        log_event("runtime_queue_worker_running", asdict(target))

        target.status = "completed"
        target.reason = "validated and completed in simulation mode"
        target.updated_at = now()
        self.write_queue(items)
        RuntimeWorkerState.write(
            worker_status="idle",
            last_command=target.command,
            last_result="completed"
        )

        log_event("runtime_queue_worker_completed", asdict(target))

        return {"processed": True, "status": "completed", "item": asdict(target)}


if __name__ == "__main__":
    result = RuntimeQueueWorker().process_once()
    print(json.dumps(result, ensure_ascii=False, indent=2))
