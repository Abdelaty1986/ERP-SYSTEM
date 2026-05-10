from jarvis.core.agent_registry import AgentRegistry
from jarvis.core.decision_engine import DecisionEngine
from jarvis.core.file_inspector import FileInspector
from jarvis.core.memory import JarvisMemory
from jarvis.core.planning_engine import PlanningEngine
from jarvis.core.patch_planner import PatchPlanner
from jarvis.execution.safe_patch_generator import SafePatchGenerator
from jarvis.execution.diff_renderer import DiffRenderer
from jarvis.execution.patch_validator import PatchValidator

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
        self.patch_planner = PatchPlanner()
        self.inspector = FileInspector(".")
        self.safe_patch_generator = SafePatchGenerator(".")
        self.patch_validator = PatchValidator()

    def build_agents(self):
        instances = []

        for agent in self.registry.get_enabled_agents():
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
        inspections = self.inspector.inspect_many(plan["expected_files"])
        patch_plan = self.patch_planner.create_patch_plan(task, plan)

        safe_patch_plan = self.safe_patch_generator.generate_patch_plan(
            task=task,
            expected_files=plan["expected_files"],
            inspections=inspections
        )

        patch_validation = self.patch_validator.validate(
            safe_patch_plan
        )

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
            "file_inspections": inspections,
            "patch_plan": patch_plan,
            "safe_patch_plan": safe_patch_plan,
            "patch_validation": patch_validation,
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

    print("\nExpected Files:")
    for item in report["plan"]["expected_files"]:
        print(f"- {item}")

    print("\nFile Inspections:")
    for item in report["file_inspections"]:
        print(f"- {item['file']}: {item['type']}")

    print("\nDecision:")
    print(report["decision"]["status"])

    print("\nSafe Patch Proposal:")
    print("-" * 40)
    for patch in report["safe_patch_plan"]["patches"]:
        print(f"- {patch['file_path']} | {patch['change_type']} | {patch['risk_level']}")

    print("\nPatch Validation:")
    print("-" * 40)
    print(report["patch_validation"]["status"])
    print(report["patch_validation"]["summary"])
