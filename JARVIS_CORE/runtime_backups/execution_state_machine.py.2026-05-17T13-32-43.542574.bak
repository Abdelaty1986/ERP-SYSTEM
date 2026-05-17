from datetime import datetime, timezone


class ExecutionStateMachine:
    STATES = [
        "RECEIVED",
        "PARSED",
        "INTENT_DETECTED",
        "RISK_ANALYZED",
        "PLAN_GENERATED",
        "WAITING_APPROVAL",
        "EXECUTING",
        "COMPLETED",
        "FAILED",
        "ROLLED_BACK",
    ]

    def build(self, command: str):
        command = command or ""

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "command": command,
            "state": "WAITING_APPROVAL",
            "execution_mode": "approval_driven_execution",
            "bounded": True,
            "dangerous_execution": False,
            "rollback_required": True,
            "steps": [
                "RECEIVED",
                "PARSED",
                "INTENT_DETECTED",
                "RISK_ANALYZED",
                "PLAN_GENERATED",
                "WAITING_APPROVAL",
            ],
        }
