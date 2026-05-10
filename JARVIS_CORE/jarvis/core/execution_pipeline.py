from jarvis.core.execution_state import ExecutionStateMachine
from jarvis.execution.git_commit_engine import GitCommitEngine
from jarvis.execution.real_apply_policy_manager import RealApplyPolicyManager
from jarvis.execution.real_apply_applier import RealApplyApplier
from jarvis.execution.execution_git_tagger import ExecutionGitTagger
from jarvis.execution.ephemeral_branch_manager import EphemeralBranchManager


class ExecutionPipeline:
    """
    Central runtime workflow pipeline for Jarvis.
    """

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    def run(
        self,
        task: str,
        human_approval: str | None = None,
        real_apply_mode: str = "simulation_only",
        tag_execution: bool = False,
        isolated_branch: bool = False,
    ):
        state_machine = ExecutionStateMachine()

        voice = self.orchestrator.voice_runtime

        voice.announce_start(task)

        state_machine.transition_to(
            "PLANNING",
            "Task processing started."
        )

        voice.announce_planning()

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

        voice.announce_validation()

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
                patch_validation=patch_validation,
                human_approval=human_approval
            )
        )

        if approval_decision["status"] == "waiting_for_human_approval":
            state_machine.transition_to(
                "WAITING_APPROVAL",
                "Human approval is required."
            )
        elif approval_decision["status"] == "approved":
            state_machine.transition_to(
                "TEST_DISCOVERY",
                "Human approval received."
            )
        else:
            state_machine.transition_to(
                "APPLY_BLOCKED",
                approval_decision.get("message", "Approval blocked.")
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

        ephemeral_branch = EphemeralBranchManager(".").create_branch(
            enabled=isolated_branch,
            session_id=rollback_checkpoint.get("timestamp"),
        )

        test_execution = {
            "status": "skipped",
            "summary": (
                "Tests were skipped because approval was not granted."
            ),
            "results": []
        }

        if approval_decision.get("can_apply"):
            state_machine.transition_to(
                "TESTING",
                "Approval granted. Running safe tests."
            )

            test_execution = self.orchestrator.test_runner.run_safe_tests(
                test_discovery.get("commands", [])
            )

            voice.announce_tests(
                test_execution["status"] == "passed"
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

        voice.announce_apply_mode(real_apply_mode)

        apply_readiness = (
            self.orchestrator.apply_engine.prepare_apply(
                approval_decision=approval_decision,
                patch_validation=patch_validation,
                test_execution=test_execution,
                safe_patch_plan=safe_patch_plan,
                task=task,
                real_apply_mode=real_apply_mode
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

        real_apply_switch = apply_readiness.get("real_apply_switch", {})
        receipt = apply_readiness.get("apply_safety_receipt", {})
        audit = apply_readiness.get("audit_trail", {})
        sandbox_patch_apply = apply_readiness.get("sandbox_patch_apply", {})
        post_apply_tests = apply_readiness.get("post_apply_tests", {})

        real_apply_policy = RealApplyPolicyManager(".").evaluate(
            mode=real_apply_switch.get("mode", "simulation_only"),
            human_confirmed=human_approval == "approve",
            tests_passed=test_execution.get("status") == "passed",
            sandbox_passed=(
                sandbox_patch_apply.get("ok") is True
                and post_apply_tests.get("status") == "passed"
            ),
            receipt_generated=bool(receipt.get("receipt_id")),
            audit_recorded=audit.get("status") == "recorded",
            rollback_checkpoint_created=(
                rollback_checkpoint.get("status") == "checkpoint_created"
            ),
        )

        real_apply_applier = RealApplyApplier(".").apply(
            policy_result=real_apply_policy,
            staged_files=apply_readiness.get(
                "apply_session",
                {}
            ).get("staged_files", []),
        )

        rollback_recovery = {
            "status": "not_triggered",
            "triggered": False,
            "reason": "",
            "restored_files": [],
            "failed_files": [],
        }

        if (
            real_apply_policy.get("ok") is True
            and real_apply_applier.get("ok") is not True
        ):
            rollback_recovery = (
                self.orchestrator.rollback_manager.auto_restore_files(
                    checkpoint=rollback_checkpoint,
                    files=[
                        item.get("target")
                        for item in real_apply_applier.get("applied_files", [])
                        if isinstance(item, dict) and item.get("target")
                    ],
                    reason=real_apply_applier.get("status", "real_apply_failed"),
                )
            )

        execution_tag = ExecutionGitTagger(".").create_tag(
            enabled=(
                tag_execution
                and real_apply_applier.get("ok") is True
            ),
            receipt_id=receipt.get("receipt_id"),
            commit_hash=None,
            task=task,
        )

        git_commit = GitCommitEngine(".").create_commit(
            message=f"jarvis safe apply: {task}",
            files=[
                item.get("target")
                for item in real_apply_applier.get("applied_files", [])
                if isinstance(item, dict) and item.get("target")
            ],
            real_apply_enabled=(
                real_apply_switch.get("enabled") is True
                and real_apply_applier.get("ok") is True
            ),
            tests_passed=test_execution.get("status") == "passed",
            sandbox_passed=(
                sandbox_patch_apply.get("ok") is True
                and post_apply_tests.get("status") == "passed"
            ),
            receipt_generated=bool(receipt.get("receipt_id")),
            audit_recorded=audit.get("status") == "recorded",
        )

        branch_restore = (
            EphemeralBranchManager(".").return_to_base(
                ephemeral_branch
            )
            if ephemeral_branch.get("ok")
            else {
                "status": "skipped",
                "ok": True,
                "reason": "no_ephemeral_branch",
            }
        )

        self.orchestrator.memory.remember_decision(
            project_id=self.orchestrator.project_id,
            task=task,
            decision=decision
        )

        voice.announce_completion()

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
            "ephemeral_branch": ephemeral_branch,
            "branch_restore": branch_restore,
            "apply_readiness": apply_readiness,
            "apply_contract": apply_contract_result,
            "real_apply_policy": real_apply_policy,
            "real_apply_applier": real_apply_applier,
            "rollback_recovery": rollback_recovery,
            "execution_tag": execution_tag,
            "git_commit": git_commit,
            "agent_results": results,
            "decision": decision,
            "execution_state": state_machine.snapshot(),
        }
