import argparse
import json
from pathlib import Path
from jarvis.core.agent_registry import AgentRegistry
from jarvis.core.decision_engine import DecisionEngine
from jarvis.core.file_inspector import FileInspector
from jarvis.core.memory import JarvisMemory
from jarvis.core.planning_engine import PlanningEngine
from jarvis.core.patch_planner import PatchPlanner
from jarvis.core.execution_state import ExecutionStateMachine
from jarvis.core.runtime_report_formatter import RuntimeReportFormatter
from jarvis.core.execution_pipeline import ExecutionPipeline
from jarvis.core.voice_runtime import JarvisVoiceRuntime
from jarvis.execution.safe_patch_generator import SafePatchGenerator
from jarvis.execution.diff_renderer import DiffRenderer
from jarvis.execution.patch_validator import PatchValidator
from jarvis.execution.approval_manager import ApprovalManager
from jarvis.execution.test_runner import TestRunner
from jarvis.execution.sandbox_execution_report import SandboxExecutionReport

from jarvis.execution.rollback_manager import RollbackManager
from jarvis.execution.apply_engine import ApplyEngine
from jarvis.execution.apply_contract import ControlledApplyContract

from jarvis.agents.reviewer_agent import ReviewerAgent
from jarvis.agents.groq_agent import GroqAgent
from jarvis.agents.gemini_agent import GeminiAgent
from jarvis.agents.openrouter_agent import OpenRouterAgent
from jarvis.config import RuntimeConfigManager
from jarvis.logging import RuntimeLogger
from jarvis.security import RuntimePermissionManager


class Orchestrator:
    def __init__(self, project_id="ledgerx"):
        self.runtime_config_manager = RuntimeConfigManager()
        self.runtime_config = self.runtime_config_manager.load()
        self.runtime_logger = RuntimeLogger()
        self.permission_manager = RuntimePermissionManager()
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
        self.voice_runtime = JarvisVoiceRuntime(enabled=True)

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

    def process_task(
        self,
        task,
        human_approval=None,
        real_apply_mode="simulation_only",
        tag_execution=False,
        isolated_branch=False,
    ):
        permission_profile = self.permission_manager.get_profile(
            self.runtime_config.permission_level
        )

        if real_apply_mode == "gated_apply" and not permission_profile.allow_real_apply:
            self.runtime_logger.log_event(
                event_type="runtime_permission_blocked",
                project_id=self.project_id,
                task=task,
                status="blocked",
                details={
                    "permission_level": self.runtime_config.permission_level,
                    "requested_mode": real_apply_mode,
                    "reason": "real_apply_not_allowed_by_permission_profile",
                },
            )
            real_apply_mode = "simulation_only"

        self.runtime_logger.log_event(
            event_type="runtime_task_started",
            project_id=self.project_id,
            task=task,
            status="started",
            details={
                "runtime_mode": self.runtime_config.runtime_mode,
                "permission_level": self.runtime_config.permission_level,
                "real_apply_mode": real_apply_mode,
                "tag_execution": tag_execution,
                "isolated_branch": isolated_branch,
            },
        )

        pipeline = ExecutionPipeline(self)
        report = pipeline.run(
            task,
            human_approval=human_approval,
            real_apply_mode=real_apply_mode,
            tag_execution=tag_execution,
            isolated_branch=isolated_branch,
        )

        self.runtime_logger.log_event(
            event_type="runtime_task_completed",
            project_id=self.project_id,
            task=task,
            status="completed",
            details={
                "runtime_mode": self.runtime_config.runtime_mode,
                "real_apply_mode": real_apply_mode,
                "report_type": type(report).__name__,
            },
        )

        return report


def _to_json_safe(value):
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(k): _to_json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_to_json_safe(v) for v in value]
        return str(value)


def main():
    parser = argparse.ArgumentParser(description="Run JARVIS Core orchestrator safely.")
    parser.add_argument(
        "--task",
        default="راجع شاشة الفواتير واقترح تحسين آمن",
        help="Task text to process.",
    )
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Simulate human approval.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Force proposal/report mode only. Real apply remains disabled.",
    )
    parser.add_argument(
        "--live-safe",
        action="store_true",
        help="Run a live safe sandbox-only command. Real apply remains disabled.",
    )
    parser.add_argument(
        "--target-file",
        default="JARVIS_CORE/jarvis/runtime/runtime_audit.py",
        help="Target file for live safe sandbox report.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print runtime report as JSON.",
    )
    parser.add_argument(
        "--report-file",
        default=None,
        help="Optional path to save the formatted runtime report.",
    )
    parser.add_argument(
        "--unsafe-allow-apply",
        action="store_true",
        help="Reserved flag. Real apply is intentionally disabled in this version.",
    )
    parser.add_argument(
        "--gated-apply",
        action="store_true",
        help="Enable gated real apply mode after all safety gates pass.",
    )
    parser.add_argument(
        "--tag-execution",
        action="store_true",
        help="Create local git execution tag after successful runtime.",
    )
    parser.add_argument(
        "--isolated-branch",
        action="store_true",
        help="Run execution inside isolated ephemeral git branch.",
    )

    args = parser.parse_args()

    human_approval = "approve" if args.approve else None

    real_apply_mode = "gated_apply" if args.gated_apply else "simulation_only"

    if args.live_safe:
        target = Path(args.target_file)
        if not target.exists() or not target.is_file():
            raise SystemExit(f"Target file not found: {target}")

        original = target.read_text(encoding="utf-8")
        proposed_content = (
            original
            + "\n# live_safe_review_marker: generated in sandbox only\n"
        )

        report = SandboxExecutionReport().run(
            task=args.task,
            file_path=str(target),
            proposed_content=proposed_content,
            human_approval=None,
        )
    else:
        report = Orchestrator().process_task(
            args.task,
            human_approval=human_approval,
            real_apply_mode=real_apply_mode,
            tag_execution=args.tag_execution,
            isolated_branch=args.isolated_branch,
        )

    if args.unsafe_allow_apply:
        print("WARNING: --unsafe-allow-apply is reserved. Real apply is still disabled.")

    if args.json:
        output = json.dumps(_to_json_safe(report), ensure_ascii=False, indent=2)
    else:
        output = RuntimeReportFormatter().format(report)

    if args.report_file:
        Path(args.report_file).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report_file).write_text(output, encoding="utf-8")

    print(output)


if __name__ == "__main__":
    main()