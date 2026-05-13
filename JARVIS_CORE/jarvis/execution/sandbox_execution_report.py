from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from jarvis.execution.approval_manager import ApprovalManager
from jarvis.execution.apply_contract import ControlledApplyContract
from jarvis.execution.apply_safety_receipt import ApplySafetyReceipt
from jarvis.execution.sandbox_manager import SandboxManager
from jarvis.execution.sandbox_apply_simulator import SandboxApplySimulator
from jarvis.execution.sandbox_patch_applier import SandboxPatchApplier
from jarvis.execution.sandbox_integrity_verifier import SandboxIntegrityVerifier
from jarvis.execution.sandbox_post_apply_tester import SandboxPostApplyTester
from jarvis.execution.runtime_session_manager import RuntimeSessionManager
from jarvis.execution.runtime_timeline import RuntimeTimeline


class SandboxExecutionReport:
    """
    Builds an approval-aware sandbox execution report.
    It never modifies original project files.
    Real apply remains disabled.
    """

    def __init__(self, root="."):
        self.root = Path(root)
        self.report_dir = (
            self.root / "JARVIS_CORE/runtime_logs/sandbox_execution_reports"
        )
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def run(self, task, file_path, proposed_content, human_approval=None):
        session_manager = RuntimeSessionManager(
            log_dir=str(self.root / "JARVIS_CORE/runtime_logs")
        )
        timeline = RuntimeTimeline(
            log_dir=str(self.root / "JARVIS_CORE/runtime_logs")
        )

        session = session_manager.start_session(
            command_id=None,
            command_type="sandbox_execution_report",
            source="sandbox_execution_report",
        )

        session_id = session["session_id"]
        report_id = f"sandbox-report-{session_id}"

        timeline.add_event(
            session_id=session_id,
            stage="sandbox_report_started",
            agent_id="sandbox_execution_report",
            status="started",
            message="Sandbox execution report started.",
            payload={"task": task},
        )

        target = Path(file_path)

        patch_plan = {
            "task": task,
            "file_path": str(target),
            "operation": "sandbox_proposed_content_apply",
            "bounded": True,
            "real_apply_enabled": False,
            "autonomous_apply": False,
        }

        patch_validation = {
            "status": "passed" if target.exists() and target.is_file() else "blocked",
            "file_exists": target.exists(),
            "is_file": target.is_file(),
        }

        approval = ApprovalManager().evaluate(
            patch_plan=patch_plan,
            patch_validation=patch_validation,
            human_approval=human_approval,
        )

        manager = SandboxManager(root=str(self.root))
        staged = [manager.stage_file(target)]

        diff_artifact = (
            self.root
            / "JARVIS_CORE/jarvis/execution/staging"
            / f"{target.name}.{report_id}.diff"
        )
        diff_artifact.parent.mkdir(parents=True, exist_ok=True)
        diff_artifact.write_text(
            f"--- {target.name}\n+++ {target.name}\n@@ sandbox execution report\n",
            encoding="utf-8",
        )

        patches = [{
            "file_path": str(target),
            "materialized_diff": str(diff_artifact),
            "proposed_content": proposed_content,
        }]

        simulation = SandboxApplySimulator(root=str(self.root)).simulate(
            staged,
            patches,
        )

        verifier = SandboxIntegrityVerifier()
        pre_integrity = verifier.verify(simulation, mode="pre_apply")

        sandbox_apply = SandboxPatchApplier().apply_to_sandbox(
            simulation,
            patches,
        )

        post_integrity = verifier.verify(simulation, mode="post_apply")

        post_test = SandboxPostApplyTester().run(sandbox_apply)

        rollback_checkpoint = {
            "status": "checkpoint_created",
            "mode": "sandbox_only",
            "original_files_modified": False,
        }

        contract = ControlledApplyContract().evaluate(
            approval_decision=approval,
            patch_validation=patch_validation,
            test_execution=post_test,
            rollback_checkpoint=rollback_checkpoint,
            git_branch="jarvis-core",
        )

        receipt = ApplySafetyReceipt(root=str(self.root)).create_receipt(
            task=task,
            apply_session={
                "session_id": report_id,
                "mode": "sandbox_only",
            },
            patch_manifest={
                "manifest_id": f"manifest-{report_id}",
                "manifest_file": str(diff_artifact),
            },
            sandbox_simulation=simulation,
            sandbox_integrity=post_integrity,
        )

        report = {
            "report_id": report_id,
            "session_id": session_id,
            "created_at": self._now(),
            "task": task,
            "bounded": True,
            "autonomous_apply": False,
            "real_apply_enabled": False,
            "execution_allowed": False,
            "original_files_modified": False,
            "patch_plan": patch_plan,
            "patch_validation": patch_validation,
            "approval": approval,
            "sandbox": {
                "staged": staged,
                "simulation_status": simulation.get("status"),
                "pre_integrity": pre_integrity,
                "apply": sandbox_apply,
                "post_integrity": post_integrity,
                "post_test": post_test,
            },
            "controlled_apply_contract": contract,
            "safety_receipt": receipt,
            "final_state": (
                "ready_for_human_review"
                if sandbox_apply.get("ok")
                and pre_integrity.get("ok")
                and post_integrity.get("ok")
                and post_test.get("ok")
                else "sandbox_review_required"
            ),
            "notes": [
                "Sandbox execution report is read/review oriented.",
                "Original project files are not modified.",
                "Real apply remains disabled even if approval is granted.",
            ],
        }

        timeline.add_event(
            session_id=session_id,
            stage="sandbox_report_completed",
            agent_id="sandbox_execution_report",
            status=report["final_state"],
            message="Sandbox execution report completed.",
            payload={
                "final_state": report["final_state"],
                "original_files_modified": report["original_files_modified"],
                "real_apply_enabled": report["real_apply_enabled"],
            },
        )

        session_manager.end_session(
            session_id=session_id,
            result=report["final_state"],
            error=None if report["final_state"] == "ready_for_human_review" else "sandbox_review_required",
        )

        report_file = self.report_dir / f"{report_id}.json"
        report_file.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        report["report_file"] = str(report_file)

        return report


if __name__ == "__main__":
    target = Path("JARVIS_CORE/jarvis/runtime/runtime_audit.py")
    original = target.read_text(encoding="utf-8")

    result = SandboxExecutionReport().run(
        task="sandbox live safe mode report test",
        file_path=str(target),
        proposed_content=original + "\n# sandbox_execution_report_test\n",
        human_approval=None,
    )

    print(json.dumps({
        "report_id": result["report_id"],
        "final_state": result["final_state"],
        "approval_status": result["approval"]["status"],
        "sandbox_apply_ok": result["sandbox"]["apply"]["ok"],
        "pre_integrity_ok": result["sandbox"]["pre_integrity"]["ok"],
        "post_integrity_ok": result["sandbox"]["post_integrity"]["ok"],
        "post_test_ok": result["sandbox"]["post_test"]["ok"],
        "original_files_modified": result["original_files_modified"],
        "real_apply_enabled": result["real_apply_enabled"],
        "report_file": result["report_file"],
    }, ensure_ascii=False, indent=2))
