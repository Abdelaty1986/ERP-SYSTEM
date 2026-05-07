import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent

REPORTS_DIR = ROOT / "AI_TASKS" / "validation_reports"

COMMANDS = [
    ("Run Migrations", "python migrations.py", "migrations.py"),
    ("Invoice Workflow Test", "python tests/invoice_workflow_test.py", "tests/invoice_workflow_test.py"),
]


def run_command(title, command, required_file=None):
    print(f"\\n=== {title} ===")

    if required_file and not (ROOT / required_file).exists():
        print("SKIPPED")
        return {
            "title": title,
            "command": command,
            "status": "SKIPPED",
            "output": f"Skipped because required file was not found: {required_file}"
        }

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=ROOT
        )

        output = result.stdout + "\\n" + result.stderr

        status = "PASSED" if result.returncode == 0 else "FAILED"

        print(status)

        return {
            "title": title,
            "command": command,
            "status": status,
            "output": output
        }

    except Exception as e:
        return {
            "title": title,
            "command": command,
            "status": "ERROR",
            "output": str(e)
        }


def build_report(results):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    report_path = REPORTS_DIR / f"validation_report_{timestamp}.txt"

    content = "=== LEDGERX AI VALIDATION REPORT ===\\n\\n"

    for result in results:
        content += f"TEST: {result['title']}\\n"
        content += f"COMMAND: {result['command']}\\n"
        content += f"STATUS: {result['status']}\\n\\n"
        content += result["output"]
        content += "\\n\\n"
        content += "=" * 60
        content += "\\n\\n"

    report_path.write_text(content, encoding="utf-8")

    return report_path


def main():
    results = []

    for item in COMMANDS:
        title, command, required_file = item
        result = run_command(title, command, required_file)
        results.append(result)

    report = build_report(results)

    print("\\nValidation report generated:")
    print(report)


if __name__ == "__main__":
    main()
