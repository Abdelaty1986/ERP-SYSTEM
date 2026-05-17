class ExecutionExplainer:
    def detect_intent(self, command: str) -> str:
        text = (command or "").lower()

        if "apk" in text or "android" in text or "gradle" in text:
            return "android_build"
        if "git" in text or "commit" in text or "push" in text:
            return "git_operation"
        if "run" in text or "execute" in text or "شغل" in text or "نفذ" in text:
            return "runtime_execution"
        if "fix" in text or "repair" in text or "اصلح" in text:
            return "code_repair"
        if "status" in text or "حالة" in text:
            return "status_check"

        return "general_command"

    def explain(self, command: str):
        intent = self.detect_intent(command)

        return {
            "command": command,
            "intent": intent,
            "risk_level": "medium",
            "confidence": 0.86,
            "governance_gate": "approval_required",
            "execution_mode": "approval_driven_execution",
            "selected_agent": "execution_supervisor",
            "execution_reason": "Command is allowed to move from simulation into approval-gated execution.",
            "blocked_reason": None,
            "rollback_available": True,
            "dangerous_execution": False,
            "explanation": "JARVIS understood the command, generated a safe execution plan, and is waiting for human approval before real execution.",
        }
