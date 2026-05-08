from pathlib import Path
import subprocess
import json
from datetime import datetime
import sys

ROOT = Path(__file__).resolve().parent.parent.parent

HISTORY_FILE = ROOT / "AI_SYSTEM" / "logs" / "pipeline_history.json"
TASKS_DIR = ROOT / "AI_TASKS" / "pending"


def get_pending_tasks():
    if not TASKS_DIR.exists():
        return []

    return sorted([
        task.name
        for task in TASKS_DIR.glob("*.md")
    ])


def log_pipeline_run(status="SUCCESS", steps=None):
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not HISTORY_FILE.exists():
        HISTORY_FILE.write_text('{"runs": []}', encoding="utf-8")

    data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))

    pending_tasks = get_pending_tasks()

    data["runs"].append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": status,
        "pending_tasks": len(pending_tasks),
        "last_task": pending_tasks[0] if pending_tasks else None,
        "steps": steps or {}
    })

    HISTORY_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def run_step(title, command):
    print(f"\n=== {title} ===")

    result = subprocess.run(
        command,
        shell=True,
        cwd=ROOT
    )

    if result.returncode == 0:
        print("SUCCESS")
        return "SUCCESS"

    print("FAILED")
    return "FAILED"


def main():
    print("\n=== LEDGERX AI DEV PIPELINE ===")

    full_mode = "--full" in sys.argv or "--branch" in sys.argv
    branch_mode = "--branch" in sys.argv or full_mode

    steps = {}

    steps["Generate Prompt"] = run_step(
        "Generate Prompt",
        "python AI_SYSTEM/generators/ai_prompt_generator.py"
    )

    steps["Generate Risk Report"] = run_step(
        "Generate Risk Report",
        "python AI_SYSTEM/generators/risk_report_generator.py"
    )

    steps["Run Validation"] = run_step(
        "Run Validation",
        "python AI_SYSTEM/validators/validation_runner.py"
    )

    if full_mode:
        diff_command = "python AI_SYSTEM/diff_analyzer/smart_diff_analyzer.py --branch" if branch_mode else "python AI_SYSTEM/diff_analyzer/smart_diff_analyzer.py"
        test_command = "python AI_SYSTEM/testing_engine/intelligent_test_selector.py --branch" if branch_mode else "python AI_SYSTEM/testing_engine/intelligent_test_selector.py"

        steps["Smart Diff Analysis"] = run_step(
            "Smart Diff Analysis",
            diff_command
        )

        steps["Intelligent Test Selector"] = run_step(
            "Intelligent Test Selector",
            test_command
        )

        steps["Patch Planner"] = run_step(
            "Patch Planner",
            "python AI_SYSTEM/patch_engine/patch_planner.py"
        )

        steps["AI Decision Engine"] = run_step(
            "AI Decision Engine",
            "python AI_SYSTEM/decision_engine/ai_decision_engine.py"
        )

    final_status = "SUCCESS" if all(status == "SUCCESS" for status in steps.values()) else "FAILED"

    log_pipeline_run(final_status, steps)

    print("\nPipeline Finished")
    print("Final Status:", final_status)


if __name__ == "__main__":
    main()
