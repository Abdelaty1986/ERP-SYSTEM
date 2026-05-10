from dataclasses import dataclass, asdict
from typing import List, Dict, Any
from datetime import datetime


@dataclass
class StateTransition:
    from_state: str
    to_state: str
    reason: str
    timestamp: str


class ExecutionStateMachine:
    """
    Tracks Jarvis execution workflow states.
    It does NOT execute actions.
    """

    VALID_STATES = {
        "IDLE",
        "PLANNING",
        "INSPECTING",
        "PATCH_PLANNING",
        "PATCH_PROPOSAL",
        "VALIDATING",
        "REVIEWING",
        "DECIDING",
        "WAITING_APPROVAL",
        "TEST_DISCOVERY",
        "TESTING",
        "APPLY_READY",
        "APPLY_BLOCKED",
        "DONE",
        "FAILED",
    }

    ALLOWED_TRANSITIONS = {
        "IDLE": {"PLANNING"},
        "PLANNING": {"INSPECTING", "FAILED"},
        "INSPECTING": {"PATCH_PLANNING", "FAILED"},
        "PATCH_PLANNING": {"PATCH_PROPOSAL", "FAILED"},
        "PATCH_PROPOSAL": {"VALIDATING", "FAILED"},
        "VALIDATING": {"REVIEWING", "APPLY_BLOCKED", "FAILED"},
        "REVIEWING": {"DECIDING", "WAITING_APPROVAL", "TEST_DISCOVERY", "APPLY_BLOCKED", "FAILED"},
        "DECIDING": {"WAITING_APPROVAL", "APPLY_BLOCKED", "DONE", "FAILED"},
        "WAITING_APPROVAL": {"TEST_DISCOVERY", "APPLY_READY", "APPLY_BLOCKED", "DONE", "FAILED"},
        "TEST_DISCOVERY": {"DONE", "TESTING", "FAILED", "APPLY_BLOCKED", "APPLY_READY"},
        "TESTING": {"APPLY_READY", "APPLY_BLOCKED", "FAILED"},
        "APPLY_READY": {"DONE", "FAILED"},
        "APPLY_BLOCKED": {"DONE", "FAILED"},
        "DONE": set(),
        "FAILED": set(),
    }

    def __init__(self):
        self.current_state = "IDLE"
        self.transitions: List[StateTransition] = []

    def transition_to(self, next_state: str, reason: str) -> Dict[str, Any]:
        if next_state not in self.VALID_STATES:
            return self._fail(f"Invalid state: {next_state}")

        allowed = self.ALLOWED_TRANSITIONS.get(self.current_state, set())

        if next_state not in allowed:
            return self._fail(
                f"Invalid transition from {self.current_state} to {next_state}"
            )

        transition = StateTransition(
            from_state=self.current_state,
            to_state=next_state,
            reason=reason,
            timestamp=datetime.now().isoformat(timespec="seconds"),
        )

        self.transitions.append(transition)
        self.current_state = next_state

        return {
            "ok": True,
            "current_state": self.current_state,
            "transition": asdict(transition),
        }

    def mark_done(self, reason: str = "Workflow completed.") -> Dict[str, Any]:
        if self.current_state in {"DONE", "FAILED"}:
            return {
                "ok": True,
                "current_state": self.current_state,
                "message": "Workflow already ended.",
            }

        allowed = self.ALLOWED_TRANSITIONS.get(self.current_state, set())

        if "DONE" not in allowed:
            return self._fail(
                f"Cannot mark DONE from {self.current_state}"
            )

        return self.transition_to("DONE", reason)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "current_state": self.current_state,
            "transitions": [asdict(item) for item in self.transitions],
            "transition_count": len(self.transitions),
        }

    def _fail(self, message: str) -> Dict[str, Any]:
        transition = StateTransition(
            from_state=self.current_state,
            to_state="FAILED",
            reason=message,
            timestamp=datetime.now().isoformat(timespec="seconds"),
        )

        self.transitions.append(transition)
        self.current_state = "FAILED"

        return {
            "ok": False,
            "current_state": self.current_state,
            "error": message,
            "transition": asdict(transition),
        }
