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

from jarvis.execution.rollback_manager import RollbackManager
from jarvis.execution.apply_engine import ApplyEngine
from jarvis.execution.apply_contract import ControlledApplyContract

from jarvis.agents.reviewer_agent import ReviewerAgent
from jarvis.agents.groq_agent import GroqAgent
from jarvis.agents.gemini_agent import GeminiAgent
from jarvis.agents.openrouter_agent import OpenRouterAgent
from jarvis.config import RuntimeConfigManager


class Orchestrator:
    def __init__(self, project_id="ledgerx"):
        self.runtime_config_manager = RuntimeConfigManager()
        self.runtime_config = self.runtime_config_manager.load()
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
        pipeline = ExecutionPipeline(self)
        return pipeline.run(
            task,
            human_approval=human_approval,
            real_apply_mode=real_apply_mode,
            tag_execution=tag_execution,
            isolated_branch=isolated_branch,
        )


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