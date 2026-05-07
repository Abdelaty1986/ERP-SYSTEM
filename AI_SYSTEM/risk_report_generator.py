import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TASKS_DIR = ROOT / "AI_TASKS" / "pending"
MODULE_MAP = ROOT / "AI_SYSTEM" / "module_map.json"
OUTPUT_DIR = ROOT / "AI_TASKS" / "risk_reports"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def latest_task():
    tasks = sorted(TASKS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return tasks[0] if tasks else None


def detect_module(task_text, module_map):
    text = task_text.lower()

    for module_name in module_map.keys():
        if module_name.lower() in text:
            return module_name

    if "invoice" in text:
        return "sales"

    if "inventory" in text:
        return "inventory"

    if "hr" in text:
        return "hr"

    return "ui_theme"


def build_report(task_path):
    module_map = load_json(MODULE_MAP)

    task_text = task_path.read_text(encoding="utf-8")

    module = detect_module(task_text, module_map)

    module_info = module_map.get(module, {})

    report = f"""
=== LEDGERX AI RISK REPORT ===

Task:
{task_path.name}

Detected Module:
{module}

Criticality:
{module_info.get("criticality", "unknown")}

Purpose:
{module_info.get("purpose", "")}

Possible Risks:
"""

    for risk in module_info.get("risks", []):
        report += f"- {risk}\\n"

    report += "\\nCritical Files:\\n"

    for file in module_info.get("main_files", []):
        report += f"- {file}\\n"

    report += """
Required Actions:
- Review affected files
- Run migrations if needed
- Run tests
- Perform manual validation
- Keep changes inside dev-ai branch

Status:
AI analysis completed.
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_path = OUTPUT_DIR / f"{task_path.stem}_risk_report.txt"

    output_path.write_text(report, encoding="utf-8")

    return output_path


def main():
    task = latest_task()

    if not task:
        print("No pending task found.")
        return

    report = build_report(task)

    print("Risk report generated:")
    print(report)


if __name__ == "__main__":
    main()
