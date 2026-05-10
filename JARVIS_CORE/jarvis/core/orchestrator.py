from jarvis.core.agent_registry import AgentRegistry
from jarvis.core.decision_engine import DecisionEngine
from jarvis.core.memory import JarvisMemory
from jarvis.core.planning_engine import PlanningEngine

from jarvis.agents.reviewer_agent import ReviewerAgent
from jarvis.agents.groq_agent import GroqAgent
from jarvis.agents.gemini_agent import GeminiAgent
from jarvis.agents.openrouter_agent import OpenRouterAgent


class Orchestrator:
    def __init__(self, project_id="ledgerx"):
        self.project_id = project_id

        self.registry = AgentRegistry()
        self.decision_engine = DecisionEngine()
        self.memory = JarvisMemory()

        self.planner = PlanningEngine(".")

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

            if agent["id"] == "openrouter_free":
                instances.append(OpenRouterAgent())

        return instances

    def process_task(self, task):

        plan = self.planner.create_plan(task)

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
            "plan": plan,
            "agent_results": results,
            "decision": decision
        }


if __name__ == "__main__":

    orchestrator = Orchestrator()

    report = orchestrator.process_task(
        "راجع شاشة الفواتير واقترح تحسين آمن"
    )

    print("Jarvis Execution Report")
    print("=" * 40)

    print(f"Task: {report['task']}")

    print("\nPlanning Summary:")
    print(report["plan"]["project_summary"])

    print("\nExpected Files:")
    for item in report["plan"]["expected_files"]:
        print(f"- {item}")

    print("\nDecision:")
    print(report["decision"]["status"])
