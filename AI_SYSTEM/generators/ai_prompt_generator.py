import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROJECT_RULES = ROOT / "PROJECT_RULES.md"
PROJECT_CONTEXT = ROOT / "PROJECT_CONTEXT.json"
CHANGE_ANALYZER = ROOT / "AI_SYSTEM" / "CHANGE_ANALYZER.md"
MODULE_MAP = ROOT / "AI_SYSTEM" / "module_map.json"
IMPACT_MATRIX = ROOT / "AI_SYSTEM" / "impact_matrix.json"
TASKS_DIR = ROOT / "AI_TASKS" / "pending"
OUTPUT_DIR = ROOT / "AI_TASKS" / "generated_prompts"


def read_text(path):
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_json(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def latest_task():
    tasks = sorted(TASKS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return tasks[0] if tasks else None


def build_prompt(task_path):
    context = load_json(PROJECT_CONTEXT)
    module_map = load_json(MODULE_MAP)
    impact_matrix = load_json(IMPACT_MATRIX)

    task_text = read_text(task_path)

    prompt = f"""You are working on LedgerX ERP.

IMPORTANT:
Work only on branch: {context.get("ai_development_branch", "dev-ai")}
Do not modify main directly.

Before changing code, read and obey:
- PROJECT_RULES.md
- PROJECT_CONTEXT.json
- AI_SYSTEM/core/CHANGE_ANALYZER.md
- AI_SYSTEM/core/module_map.json
- AI_SYSTEM/core/impact_matrix.json
- AI_REVIEW_CHECKLIST.md

Current Task:
{task_text}

Project Context:
{json.dumps(context, ensure_ascii=False, indent=2)}

Module Map:
{json.dumps(module_map, ensure_ascii=False, indent=2)}

Impact Matrix:
{json.dumps(impact_matrix, ensure_ascii=False, indent=2)}

Required Development Behavior:
1. Analyze the request before coding.
2. Identify affected files.
3. Identify risk level.
4. Make the smallest safe change.
5. Preserve existing routes, data, permissions, accounting logic, inventory logic, and JavaScript hooks.
6. Do not perform destructive migrations.
7. Do not rewrite unrelated code.

Required Output:
- Summary of changes
- Files changed
- Risk analysis
- Tests run
- Manual testing checklist
- Any known limitations

Validation:
Run:
python migrations.py

Then run available tests where possible.
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{task_path.stem}_prompt.txt"
    output_path.write_text(prompt, encoding="utf-8")
    return output_path


def main():
    task = latest_task()
    if not task:
        print("No pending tasks found.")
        return

    output = build_prompt(task)
    print(f"Generated prompt:")
    print(output)


if __name__ == "__main__":
    main()
