from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class ApprovalTransitionStabilizer:
    def __init__(self, root: str = "JARVIS_CORE"):
        self.root = Path(root)
        self.transition_file = self.root / "runtime_memory" / "approval_transition_memory.json"
        self.output_file = self.root / "runtime_logs" / "approval_transition_stability.json"

    def _load_json(self, path: Path, fallback):
        if not path.exists():
            return fallback
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return fallback

    def analyze(self):
        data = self._load_json(self.transition_file, {})

        transitions = data.get("transitions", [])
        current_state = data.get("current_state", "locked")

        unsafe_unlock = current_state not in ["locked", "authorized_locked", "expired_locked", "revoked_locked"]

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stabilizer": "approval_transition_stabilizer",
            "bounded": True,
            "real_apply_enabled": False,
            "autonomous_apply": False,
            "execution_unlock_allowed": False,
            "current_state": current_state,
            "transition_count": len(transitions),
            "unsafe_unlock_detected": unsafe_unlock,
            "stability_state": "stable" if not unsafe_unlock else "needs_review",
            "recommendation": "continue_to_runtime_aggregation" if not unsafe_unlock else "review_transition_state",
        }

        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.output_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result


if __name__ == "__main__":
    print(json.dumps(ApprovalTransitionStabilizer().analyze(), indent=2))
