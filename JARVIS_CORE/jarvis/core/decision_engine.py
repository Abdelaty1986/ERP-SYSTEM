class DecisionEngine:
    def evaluate(self, agent_results):
        if not agent_results:
            return {
                "status": "rejected",
                "reason": "No agent results were provided.",
                "can_apply": False
            }

        risk_levels = []

        for item in agent_results:
            result = item.get("result", {})
            risk_levels.append(result.get("risk_level", "unknown"))

        if "high" in risk_levels or "unknown" in risk_levels:
            status = "needs_human_review"
            can_apply = False
        else:
            status = "ready_for_planning"
            can_apply = False

        return {
            "status": status,
            "risk_levels": risk_levels,
            "can_apply": can_apply,
            "reason": "Jarvis never applies changes directly without tests and user approval."
        }


if __name__ == "__main__":
    sample_results = [
        {
            "agent": "Local Reviewer Agent",
            "result": {
                "risk_level": "medium"
            }
        }
    ]

    decision = DecisionEngine().evaluate(sample_results)
    print(decision)
