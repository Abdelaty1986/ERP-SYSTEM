from jarvis.core.agent_registry import AgentRegistry
from jarvis.core.decision_engine import DecisionEngine
from jarvis.core.file_inspector import FileInspector
from jarvis.core.memory import JarvisMemory
from jarvis.core.planning_engine import PlanningEngine
from jarvis.core.patch_planner import PatchPlanner
from jarvis.core.execution_state import ExecutionStateMachine
from jarvis.execution.safe_patch_generator import SafePatchGenerator
from jarvis.execution.diff_renderer import DiffRenderer
from jarvis.execution.patch_validator import PatchValidator
from jarvis.execution.approval_manager import ApprovalManager
from jarvis.execution.test_runner import TestRunner

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
        self.approval_manager = ApprovalManager()
        self.test_runner = TestRunner(".")

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
        state_machine = ExecutionStateMachine()
        state_machine.transition_to("PLANNING", "Task processing started.")
        plan = self.planner.create_plan(task)
        state_machine.transition_to("INSPECTING", "Planning completed.")
        inspections = self.inspector.inspect_many(plan["expected_files"])
        state_machine.transition_to("PATCH_PLANNING", "File inspection completed.")
        patch_plan = self.patch_planner.create_patch_plan(task, plan)
        state_machine.transition_to("PATCH_PROPOSAL", "Patch planning completed.")

        safe_patch_plan = self.safe_patch_generator.generate_patch_plan(
            task=task,
            expected_files=plan["expected_files"],
            inspections=inspections
        )
        state_machine.transition_to("VALIDATING", "Safe patch proposal generated.")

        patch_validation = self.patch_validator.validate(
            safe_patch_plan
        )

        if patch_validation["status"] == "blocked":
            state_machine.transition_to("APPLY_BLOCKED", "Patch validation blocked execution.")
        else:
            state_machine.transition_to("REVIEWING", "Patch validation completed.")

        approval_decision = self.approval_manager.evaluate(
            patch_plan=safe_patch_plan,
            patch_validation=patch_validation
        )

        if approval_decision["status"] == "waiting_for_human_approval":
            state_machine.transition_to("WAITING_APPROVAL", "Human approval is required.")
        elif approval_decision["status"] == "approved":
            state_machine.transition_to("TEST_DISCOVERY", "Human approval received.")
        else:
            state_machine.transition_to("APPLY_BLOCKED", approval_decision["message"])

        test_discovery = self.test_runner.discover_tests()
        if state_machine.current_state == "WAITING_APPROVAL":
            state_machine.transition_to("TEST_DISCOVERY", "Discovered available tests while waiting for approval.")
        state_machine.mark_done("Orchestrator report completed.")

        results = []

        for agent in self.build_agents():
            results.append({
                "agent": agent.name,
                "result": agent.think(task)
            })

        if state_machine.current_state == "REVIEWING":
            state_machine.transition_to("DECIDING", "Agent review completed.")
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
            "approval_decision": approval_decision,
            "test_discovery": test_discovery,
            "execution_state": state_machine.snapshot(),
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

    print("\nApproval Status:")
    print("-" * 40)
    print(report["approval_decision"]["status"])
    print(report["approval_decision"]["message"])

    print("\nTest Discovery:")
    print("-" * 40)
    print(report["test_discovery"]["status"])
    for cmd in report["test_discovery"]["commands"]:
        print(f"- {cmd['name']}: {' '.join(cmd['command'])}")

    print("\nExecution State:")
    print("-" * 40)
    print(report["execution_state"]["current_state"])
    print(f"Transitions: {report['execution_state']['transition_count']}")
    for step in report["execution_state"]["transitions"]:
        print(f"- {step['from_state']} -> {step['to_state']} | {step['reason']}")
