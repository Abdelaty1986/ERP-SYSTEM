from jarvis.core.agent_registry import AgentRegistry
from jarvis.core.decision_engine import DecisionEngine
from jarvis.core.file_inspector import FileInspector
from jarvis.core.memory import JarvisMemory
from jarvis.core.planning_engine import PlanningEngine
from jarvis.core.patch_planner import PatchPlanner
from jarvis.core.execution_state import ExecutionStateMachine
from jarvis.core.runtime_report_formatter import RuntimeReportFormatter
from jarvis.core.execution_pipeline import ExecutionPipeline
from jarvis.execution.safe_patch_generator import SafePatchGenerator
from jarvis.execution.diff_renderer import DiffRenderer
from jarvis.execution.patch_validator import PatchValidator
from jarvis.execution.approval_manager import ApprovalManager
from jarvis.execution.test_runner import TestRunner

from jarvis.execution.rollback_manager import RollbackManager
from jarvis.execution.apply_engine import ApplyEngine
from jarvis.execution.apply_contract import ControlledApplyContract

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
        self.rollback_manager = RollbackManager(".")
        self.apply_engine = ApplyEngine()
        self.apply_contract = ControlledApplyContract()

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
            state_machine.transition_to(
                "TEST_DISCOVERY",
                "Discovered available tests while waiting for approval."
            )

        rollback_checkpoint = self.rollback_manager.create_checkpoint()

        test_execution = {
            "status": "skipped",
            "summary": "Tests were skipped because approval was not granted.",
            "results": []
        }

        if approval_decision.get("can_apply"):
            state_machine.transition_to(
                "TESTING",
                "Approval granted. Running safe tests."
            )

            test_execution = self.test_runner.run_safe_tests(
                test_discovery.get("commands", [])
            )

            if test_execution["status"] == "passed":
                state_machine.transition_to(
                    "APPLY_READY",
                    "All safe tests passed."
                )
            else:
                state_machine.transition_to(
                    "APPLY_BLOCKED",
                    "Safe tests failed."
                )


        apply_readiness = self.apply_engine.prepare_apply(
            approval_decision=approval_decision,
            patch_validation=patch_validation,
            test_execution=test_execution
        )

        apply_contract_result = self.apply_contract.evaluate(
            approval_decision=approval_decision,
            patch_validation=patch_validation,
            test_execution=test_execution,
            rollback_checkpoint=rollback_checkpoint,
            git_branch="jarvis-core"
        )

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
            "test_execution": test_execution,
            "rollback_checkpoint": rollback_checkpoint,
            "apply_readiness": apply_readiness,
            "apply_contract": apply_contract_result,
            "execution_state": state_machine.snapshot(),
            "agent_results": results,
            "decision": decision
        }

if __name__ == "__main__":
    orchestrator = Orchestrator()

    report = orchestrator.process_task(
        "راجع شاشة الفواتير واقترح تحسين آمن"
    )

    formatter = RuntimeReportFormatter()
    print(formatter.format(report))
