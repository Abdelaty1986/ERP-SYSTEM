from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import uuid


MEMORY_PATH = Path("JARVIS_CORE/runtime_memory/approval_gateway.json")


@dataclass
class ApprovalSession:
    session_id: str
    approval_state: str
    authorization_scope: str
    staged_unlock_state: str
    execution_lock_state: str
    rollback_binding: str
    expires_at: str
    bounded: bool
    autonomous_apply: bool
    created_at: str


class ApprovalGatewayEngine:
    """
    Bounded approval gateway runtime.

    This engine does NOT execute code.
    This engine does NOT modify files.
    This engine only prepares governed approval sessions.
    """

    def __init__(self, memory_path: Path = MEMORY_PATH):
        self.memory_path = memory_path
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)

    def create_session(
        self,
        authorization_scope: str = "execution_preparation_only",
        rollback_binding: str = "required",
        ttl_minutes: int = 30,
    ) -> dict:

        now = datetime.now(timezone.utc)

        session = ApprovalSession(
            session_id=f"approval-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}",
            approval_state="awaiting_human_approval",
            authorization_scope=authorization_scope,
            staged_unlock_state="locked",
            execution_lock_state="locked",
            rollback_binding=rollback_binding,
            expires_at=(now + timedelta(minutes=ttl_minutes)).isoformat(),
            bounded=True,
            autonomous_apply=False,
            created_at=now.isoformat(),
        )

        payload = {
            "gateway_state": "active",
            "latest_session": asdict(session),
            "governance": {
                "human_approval_required": True,
                "autonomous_apply_allowed": False,
                "bounded_authorization": True,
                "rollback_required": True,
                "real_apply_enabled": False,
            },
            "updated_at": now.isoformat(),
        }

        self.memory_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return payload

    def load_state(self) -> dict:
        if not self.memory_path.exists():
            return self.create_session()

        try:
            raw = self.memory_path.read_text(encoding="utf-8").strip()
            if not raw:
                return self.create_session()
            return json.loads(raw)
        except Exception:
            return self.create_session()


if __name__ == "__main__":
    engine = ApprovalGatewayEngine()
    result = engine.create_session()

    print(json.dumps(result, ensure_ascii=False, indent=2))
