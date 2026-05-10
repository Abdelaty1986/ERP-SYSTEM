from jarvis.core.agent_registry import AgentRegistry
from jarvis.core.decision_engine import DecisionEngine
from jarvis.core.memory import JarvisMemory
from jarvis.agents.reviewer_agent import ReviewerAgent
from jarvis.agents.groq_agent import GroqAgent
from jarvis.agents.gemini_agent import GeminiAgent


class Orchestrator:
    def __init__(self, project_id="ledgerx"):
        self.project_id = project_id
        self.registry = AgentRegistry()
        self.decision_engine = DecisionEngine()
        self.memory = JarvisMemory()

    def build_agents(self):
        enabled_agents = self.registry.get_enabled_agents()
        instances = []

        for agent in enabled_agents:
            if agent["id"] == "local_reviewer":
                instances.append(ReviewerAgent())

            if agent["id"] == "groq_free":
                instances.append(GroqAgent())

            if agent["id"] == "gemini_free":
                instances.append(GeminiAgent())

        return instances

    def process_task(self, task):
        results = []

        for agent in self.build_agents():
            results.append({
                "agent": agent.name,
                "result": agent.think(task)
            })

        decision = self.decision_engine.evaluate(results)

        self.memory.remember_decision(
            project_id=self.project_id,
            task=task,
            decision=decision
        )

        return {
            "project_id": self.project_id,
            "task": task,
            "agent_results": results,
            "decision": decision
        }


if __name__ == "__main__":
    orchestrator = Orchestrator()
    report = orchestrator.process_task("Test Gemini integration safely")
    print(report)
