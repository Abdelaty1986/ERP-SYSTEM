from jarvis.core.execution_state import ExecutionStateMachine


class ExecutionPipeline:
    """
    Central runtime workflow pipeline for Jarvis.
    """

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    def run(self, task: str):
        state_machine = ExecutionStateMachine()

        state_machine.transition_to(
            "PLANNING",
            "Task processing started."
        )

        plan = self.orchestrator.planner.create_plan(task)

        state_machine.transition_to(
            "INSPECTING",
            "Planning completed."
        )

        inspections = self.orchestrator.inspector.inspect_many(
            plan["expected_files"]
        )

        state_machine.transition_to(
            "PATCH_PLANNING",
            "File inspection completed."
        )

        patch_plan = self.orchestrator.patch_planner.create_patch_plan(
            task,
            plan
        )

        state_machine.transition_to(
            "PATCH_PROPOSAL",
            "Patch planning completed."
        )

        safe_patch_plan = (
            self.orchestrator.safe_patch_generator.generate_patch_plan(
                task=task,
                expected_files=plan["expected_files"],
                inspections=inspections
            )
        )

        state_machine.transition_to(
            "VALIDATING",
            "Safe patch proposal generated."
        )

        patch_validation = (
            self.orchestrator.patch_validator.validate(
                safe_patch_plan
            )
        )

        if patch_validation["status"] == "blocked":
            state_machine.transition_to(
                "APPLY_BLOCKED",
                "Patch validation blocked execution."
            )
        else:
            state_machine.transition_to(
                "REVIEWING",
                "Patch validation completed."
            )

        results = []

        for agent in self.orchestrator.build_agents():
            results.append({
                "agent": agent.name,
                "result": agent.think(task)
            })

        decision = self.orchestrator.decision_engine.evaluate(
            results
        )

        approval_decision = (
            self.orchestrator.approval_manager.evaluate(
                patch_plan=safe_patch_plan,
                patch_validation=patch_validation
            )
        )

        if approval_decision["status"] == "waiting_for_human_approval":
            state_machine.transition_to(
                "WAITING_APPROVAL",
                "Human approval is required."
            )

        test_discovery = (
            self.orchestrator.test_runner.discover_tests()
        )

        if state_machine.current_state == "WAITING_APPROVAL":
            state_machine.transition_to(
                "TEST_DISCOVERY",
                "Discovered available tests while waiting for approval."
            )

        rollback_checkpoint = (
            self.orchestrator.rollback_manager.create_checkpoint()
        )

        test_execution = {
            "status": "skipped",
            "summary": (
                "Tests were skipped because approval was not granted."
            ),
            "results": []
        }

        apply_readiness = (
            self.orchestrator.apply_engine.prepare_apply(
                approval_decision=approval_decision,
                patch_validation=patch_validation,
                test_execution=test_execution
            )
        )

        apply_contract_result = (
            self.orchestrator.apply_contract.evaluate(
                approval_decision=approval_decision,
                patch_validation=patch_validation,
                test_execution=test_execution,
                rollback_checkpoint=rollback_checkpoint,
                git_branch="jarvis-core"
            )
        )

        self.orchestrator.memory.remember_decision(
            project_id=self.orchestrator.project_id,
            task=task,
            decision=decision
        )

        state_machine.mark_done(
            "Orchestrator report completed."
        )

        return {
            "project_id": self.orchestrator.project_id,
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
            "agent_results": results,
            "decision": decision,
            "execution_state": state_machine.snapshot(),
        }
