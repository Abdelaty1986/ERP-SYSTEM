from typing import Dict, Any, Optional

from jarvis.execution.apply_session import ApplySession
from jarvis.execution.sandbox_manager import SandboxManager
from jarvis.execution.patch_materializer import PatchMaterializer
from jarvis.execution.patch_manifest import PatchManifest
from jarvis.execution.sandbox_apply_simulator import SandboxApplySimulator
from jarvis.execution.sandbox_integrity_verifier import SandboxIntegrityVerifier
from jarvis.execution.apply_safety_receipt import ApplySafetyReceipt
from jarvis.execution.audit_trail import AuditTrail
from jarvis.execution.apply_finalizer import ApplyFinalizer
from jarvis.execution.system_health_check import ExecutionSystemHealthCheck
from jarvis.execution.real_apply_switch import RealApplySwitch
from jarvis.execution.sandbox_patch_applier import SandboxPatchApplier
from jarvis.execution.sandbox_post_apply_tester import SandboxPostApplyTester
from jarvis.execution.patch_intelligence import PatchIntelligence
from jarvis.execution.diff_quality_gate import DiffQualityGate


class ApplyEngine:
    """
    Controlled apply preparation engine.
    Real patch application is intentionally disabled for safety.

    This engine only prepares an apply session, backups, staging metadata,
    and safety status. It does not modify project source files.
    """

    def __init__(self, root="."):
        self.root = root
        self.sandbox_manager = SandboxManager(root)
        self.materializer = PatchMaterializer(root)
        self.manifest_manager = PatchManifest(root)
        self.simulator = SandboxApplySimulator(root)
        self.integrity_verifier = SandboxIntegrityVerifier()
        self.receipt_manager = ApplySafetyReceipt(root)
        self.audit_trail = AuditTrail(root)
        self.finalizer = ApplyFinalizer()
        self.health_check = ExecutionSystemHealthCheck(root)
        self.real_apply_switch = RealApplySwitch()
        self.sandbox_patch_applier = SandboxPatchApplier()
        self.post_apply_tester = SandboxPostApplyTester()
        self.patch_intelligence = PatchIntelligence()
        self.diff_quality_gate = DiffQualityGate()

    def prepare_apply(
        self,
        approval_decision: Dict[str, Any],
        patch_validation: Dict[str, Any],
        test_execution: Dict[str, Any],
        safe_patch_plan: Optional[Dict[str, Any]] = None,
        task: str = "",
        real_apply_mode: str = "simulation_only",
    ) -> Dict[str, Any]:

        if not approval_decision.get("can_apply"):
            return {
                "status": "blocked",
                "reason": "Approval not granted.",
                "can_apply": False,
            }

        if patch_validation.get("status") == "blocked":
            return {
                "status": "blocked",
                "reason": "Patch validation failed.",
                "can_apply": False,
            }

        if test_execution.get("status") != "passed":
            return {
                "status": "blocked",
                "reason": "Safe tests did not pass.",
                "can_apply": False,
            }

        session = ApplySession(task=task or "unspecified task")
        session.mark_validation_passed()
        session.mark_approval_received()
        session.mark_tests_passed()
        session.set_status("simulation_ready")

        staged_targets = []

        materialized_patches = []

        quality_gate = (
            self.diff_quality_gate.evaluate_plan(safe_patch_plan)
            if safe_patch_plan
            else {
                "status": "missing_patch_plan",
                "approved_count": 0,
                "blocked_count": 0,
                "results": [],
                "message": "No safe patch plan provided.",
            }
        )

        if safe_patch_plan:
            for patch in safe_patch_plan.get("patches", []):
                file_path = patch.get("file_path")

                if not file_path:
                    continue

                patch_analysis = self.diff_quality_gate.evaluate_patch(patch)

                if patch_analysis.get("can_materialize"):
                    materialized = (
                        self.materializer.materialize_patch(patch)
                    )

                    materialized_patches.append(materialized)

                staged_data = self.sandbox_manager.stage_file(file_path)

                if staged_data and staged_data.get("status") == "staged":
                    session.add_staged_file(staged_data)
                    staged_targets.append(file_path)

                elif staged_data:
                    session.add_skipped_target(staged_data)

        manifest = self.manifest_manager.create_manifest(
            task=task,
            materialized_patches=materialized_patches,
            staged_targets=staged_targets,
        )

        simulation_result = self.simulator.simulate(
            staged_files=session.staged_files,
            materialized_patches=materialized_patches,
        )

        integrity_result = self.integrity_verifier.verify(
            simulation_result
        )

        sandbox_patch_apply = (
            self.sandbox_patch_applier.apply_to_sandbox(
                simulation_result=simulation_result,
                materialized_patches=materialized_patches,
            )
        )

        post_apply_tests = self.post_apply_tester.run(
            sandbox_patch_apply
        )

        receipt = self.receipt_manager.create_receipt(
            task=task,
            apply_session=session.to_dict(),
            patch_manifest=manifest,
            sandbox_simulation=simulation_result,
            sandbox_integrity=integrity_result,
        )

        audit_result = self.audit_trail.record(
            event_type="controlled_apply_simulation",
            payload={
                "task": task,
                "session_id": session.session_id,
                "receipt_id": receipt.get("receipt_id"),
                "integrity_ok": integrity_result.get("ok"),
                "manifest_id": manifest.get("manifest_id"),
            }
        )

        finalization = self.finalizer.finalize(
            apply_session=session.to_dict(),
            patch_manifest=manifest,
            sandbox_simulation=simulation_result,
            sandbox_integrity=integrity_result,
            safety_receipt=receipt,
            audit_trail=audit_result,
        )

        health_status = self.health_check.run()
        real_apply_status = self.real_apply_switch.status(
            mode_override=real_apply_mode
        )

        return {
            "status": "ready_for_controlled_apply",
            "can_apply": False,
            "execution_mode": "simulation_only",
            "message": (
                "All safety gates passed. "
                "Apply simulation session prepared. "
                "Real apply engine is intentionally disabled."
            ),
            "apply_session": session.to_dict(),
            "staged_targets": staged_targets,
            "diff_quality_gate": quality_gate,
            "materialized_patches": materialized_patches,
            "patch_manifest": manifest,
            "sandbox_apply_simulation": simulation_result,
            "sandbox_integrity": integrity_result,
            "sandbox_patch_apply": sandbox_patch_apply,
            "post_apply_tests": post_apply_tests,
            "apply_safety_receipt": receipt,
            "audit_trail": audit_result,
            "apply_finalization": finalization,
            "system_health": health_status,
            "real_apply_switch": real_apply_status,
        }
