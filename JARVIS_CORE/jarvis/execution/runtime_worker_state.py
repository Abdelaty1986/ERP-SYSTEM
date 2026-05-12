from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any


STATE_FILE = Path("JARVIS_CORE/runtime_logs/runtime_worker_state.json")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class RuntimeWorkerState:

    @staticmethod
    def read() -> Dict[str, Any]:
        if not STATE_FILE.exists():
            return {
                "worker_status": "idle",
                "last_heartbeat": None,
                "last_command": None,
                "last_result": None,
            }

        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {
                "worker_status": "corrupted",
                "last_heartbeat": None,
                "last_command": None,
                "last_result": None,
            }

    @staticmethod
    def heartbeat(worker_status: str = "idle") -> None:
        current = RuntimeWorkerState.read()

        RuntimeWorkerState.write(
            worker_status=worker_status,
            last_command=current.get("last_command"),
            last_result=current.get("last_result"),
        )

    @staticmethod
    def write(
        worker_status: str,
        last_command: str | None = None,
        last_result: str | None = None,
    ) -> None:

        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "worker_status": worker_status,
            "last_heartbeat": utc_now(),
            "last_command": last_command,
            "last_result": last_result,
        }

        STATE_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
