from pathlib import Path
import subprocess
import json
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent.parent




HISTORY_FILE = ROOT / "AI_SYSTEM" / "logs" / "pipeline_history.json"


def log_pipeline_run(status="SUCCESS"):
    if not HISTORY_FILE.exists():
        HISTORY_FILE.write_text('{"runs": []}', encoding="utf-8")

    data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))

    data["runs"].append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": status
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
    else:
        print("FAILED")


def main():
    print("\n=== LEDGERX AI DEV PIPELINE ===")

    run_step(
        "Generate Prompt",
        "python AI_SYSTEM/generators/ai_prompt_generator.py"
    )

    run_step(
        "Generate Risk Report",
        "python AI_SYSTEM/generators/risk_report_generator.py"
    )

    run_step(
        "Run Validation",
        "python AI_SYSTEM/validators/validation_runner.py"
    )

    log_pipeline_run("SUCCESS")

    print("\nPipeline Finished")


if __name__ == "__main__":
    main()
