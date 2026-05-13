from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json


GATEWAY_PATH = Path("JARVIS_CORE/runtime_memory/approval_gateway.json")
LINEAGE_PATH = Path("JARVIS_CORE/runtime_memory/approval_lineage.json")
TRANSITION_PATH = Path("JARVIS_CORE/runtime_memory/approval_transitions.json")


class ApprovalTransitionEngine:
    """
    Approval Session Transition Runtime.

    This engine manages approval-state transitions only.
    It does NOT execute code.
    It does NOT apply patches.
    It does NOT unlock real execution.
    """

    ALLOWED_TRANSITIONS = {
        "awaiting_human_approval": ["authorized", "revoked", "expired"],
        "authorized": ["locked", "revoked", "expired"],
        "locked": ["revoked", "expired"],
        "revoked": [],
        "expired": [],
    }

    def __init__(
        self,
        gateway_path: Path = GATEWAY_PATH,
        lineage_path: Path = LINEAGE_PATH,
        transition_path: Path = TRANSITION_PATH,
    ):
        self.gateway_path = gateway_path
        self.lineage_path = lineage_path
        self.transition_path = transition_path
        self.transition_path.parent.mkdir(parents=True, exist_ok=True)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load_json(self, path: Path, fallback: dict) -> dict:
        if not path.exists():
            return fallback
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return fallback

    def _write_json(self, path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def transition(self, target_state: str = "locked", reason: str = "governed_transition") -> dict:
        gateway = self._load_json(self.gateway_path, {})
        session = gateway.get("latest_session") or {}

        current_state = session.get("approval_state", "awaiting_human_approval")
        allowed = self.ALLOWED_TRANSITIONS.get(current_state, [])

        approved = target_state in allowed

        # Safety rule: even when authorized, execution remains locked.
        execution_lock_state = "locked"
        staged_unlock_state = "locked"

        event = {
            "event_type": "approval_state_transition",
            "session_id": session.get("session_id", "none"),
            "from_state": current_state,
            "to_state": target_state if approved else current_state,
            "requested_target_state": target_state,
            "transition_allowed": approved,
            "reason": reason,
            "execution_lock_state": execution_lock_state,
            "staged_unlock_state": staged_unlock_state,
            "bounded": True,
            "autonomous_apply": False,
            "real_apply_enabled": False,
            "transitioned_at": self._now(),
        }

        if session:
            session["approval_state"] = event["to_state"]
            session["execution_lock_state"] = execution_lock_state
            session["staged_unlock_state"] = staged_unlock_state
            session["autonomous_apply"] = False
            session["bounded"] = True

            gateway["latest_session"] = session
            gateway["gateway_state"] = "active"
            gateway["updated_at"] = self._now()

            governance = gateway.setdefault("governance", {})
            governance["human_approval_required"] = True
            governance["autonomous_apply_allowed"] = False
            governance["bounded_authorization"] = True
            governance["rollback_required"] = True
            governance["real_apply_enabled"] = False

            self._write_json(self.gateway_path, gateway)

        transitions = self._load_json(
            self.transition_path,
            {
                "transition_state": "initialized",
                "bounded": True,
                "autonomous_apply": False,
                "events": [],
                "latest_transition": None,
                "updated_at": None,
            },
        )

        events = transitions.get("events", [])
        events.append(event)
        events = events[-100:]

        payload = {
            "transition_state": "active",
            "bounded": True,
            "autonomous_apply": False,
            "latest_transition": event,
            "events": events,
            "event_count": len(events),
            "governance": {
                "human_approval_required": True,
                "execution_unlock_allowed": False,
                "real_apply_enabled": False,
                "rollback_trace_required": True,
                "transition_replay_ready": True,
            },
            "updated_at": self._now(),
        }

        self._write_json(self.transition_path, payload)

        lineage = self._load_json(self.lineage_path, {})
        lineage_events = lineage.get("events", [])
        lineage_events.append({
            "event_type": "approval_transition_recorded",
            "session_id": event["session_id"],
            "from_state": event["from_state"],
            "to_state": event["to_state"],
            "transition_allowed": event["transition_allowed"],
            "execution_lock_state": event["execution_lock_state"],
            "bounded": True,
            "autonomous_apply": False,
            "observed_at": self._now(),
        })
        lineage["events"] = lineage_events[-100:]
        lineage["latest_event"] = lineage["events"][-1]
        lineage["event_count"] = len(lineage["events"])
        lineage["lineage_state"] = "active"
        lineage["updated_at"] = self._now()
        self._write_json(self.lineage_path, lineage)

        return payload


if __name__ == "__main__":
    result = ApprovalTransitionEngine().transition(
        target_state="authorized",
        reason="human_authorization_simulated_without_unlock",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
