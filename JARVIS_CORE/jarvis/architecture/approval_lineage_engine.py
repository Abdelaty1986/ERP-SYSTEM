from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json


LINEAGE_PATH = Path("JARVIS_CORE/runtime_memory/approval_lineage.json")
GATEWAY_PATH = Path("JARVIS_CORE/runtime_memory/approval_gateway.json")


class ApprovalLineageEngine:
    """
    Approval Session Lineage Runtime.

    This engine only records approval session history.
    It does NOT unlock execution.
    It does NOT apply patches.
    It does NOT modify project files.
    """

    def __init__(
        self,
        lineage_path: Path = LINEAGE_PATH,
        gateway_path: Path = GATEWAY_PATH,
    ):
        self.lineage_path = lineage_path
        self.gateway_path = gateway_path
        self.lineage_path.parent.mkdir(parents=True, exist_ok=True)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load_json(self, path: Path, fallback: dict) -> dict:
        if not path.exists():
            return fallback
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return fallback

    def build_lineage(self) -> dict:
        gateway = self._load_json(self.gateway_path, {})
        session = gateway.get("latest_session") or {}

        event = {
            "event_type": "approval_session_observed",
            "session_id": session.get("session_id", "none"),
            "approval_state": session.get("approval_state", "unknown"),
            "authorization_scope": session.get("authorization_scope", "unknown"),
            "execution_lock_state": session.get("execution_lock_state", "locked"),
            "staged_unlock_state": session.get("staged_unlock_state", "locked"),
            "rollback_binding": session.get("rollback_binding", "required"),
            "bounded": session.get("bounded", True),
            "autonomous_apply": session.get("autonomous_apply", False),
            "observed_at": self._now(),
        }

        lineage = self._load_json(
            self.lineage_path,
            {
                "lineage_state": "initialized",
                "bounded": True,
                "autonomous_apply": False,
                "events": [],
                "latest_event": None,
                "updated_at": None,
            },
        )

        events = lineage.get("events", [])
        events.append(event)
        events = events[-50:]

        payload = {
            "lineage_state": "active",
            "bounded": True,
            "autonomous_apply": False,
            "latest_event": event,
            "events": events,
            "event_count": len(events),
            "governance": {
                "human_approval_required": True,
                "execution_unlock_allowed": False,
                "real_apply_enabled": False,
                "rollback_trace_required": True,
                "lineage_replay_ready": True,
            },
            "updated_at": self._now(),
        }

        self.lineage_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return payload


if __name__ == "__main__":
    result = ApprovalLineageEngine().build_lineage()
    print(json.dumps(result, ensure_ascii=False, indent=2))
