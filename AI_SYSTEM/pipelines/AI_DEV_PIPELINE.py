from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent.parent


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

    print("\nPipeline Finished")


if __name__ == "__main__":
    main()
