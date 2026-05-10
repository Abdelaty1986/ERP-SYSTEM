from jarvis.agents.base_agent import BaseAgent


class ReviewerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Local Reviewer Agent",
            role="Code Review and Risk Analysis",
            provider="local",
            cost="free"
        )

    def think(self, task):
        return {
            "agent": self.name,
            "task": task,
            "analysis": "Task requires review before any code change.",
            "risk_level": "medium",
            "approved_for_direct_apply": False
        }


if __name__ == "__main__":
    agent = ReviewerAgent()
    print(agent.info())
    print(agent.think("Modify invoice layout safely"))
