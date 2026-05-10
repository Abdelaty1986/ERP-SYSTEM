from jarvis.core.agent_registry import AgentRegistry
from jarvis.core.decision_engine import DecisionEngine
from jarvis.agents.reviewer_agent import ReviewerAgent


class Orchestrator:
    def __init__(self):
        self.registry = AgentRegistry()
        self.decision_engine = DecisionEngine()

    def build_agents(self):
        enabled_agents = self.registry.get_enabled_agents()
        instances = []

        for agent in enabled_agents:
            if agent["id"] == "local_reviewer":
                instances.append(ReviewerAgent())

        return instances

    def process_task(self, task):
        results = []

        for agent in self.build_agents():
            results.append({
                "agent": agent.name,
                "result": agent.think(task)
            })

        decision = self.decision_engine.evaluate(results)

        return {
            "task": task,
            "agent_results": results,
            "decision": decision
        }


if __name__ == "__main__":
    orchestrator = Orchestrator()
    report = orchestrator.process_task("Improve invoice screen layout safely")
    print(report)
