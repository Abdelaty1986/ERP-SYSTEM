from pathlib import Path
from datetime import datetime
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PENDING_DIR = PROJECT_ROOT / "AI_TASKS" / "pending"


TEMPLATE = """# Task: {title}

## Status
Pending

## Priority
{priority}

## Goal
{goal}

## Requirements
- Describe required behavior
- Preserve existing logic
- Preserve database integrity
- Preserve accounting integrity if applicable
- Keep UI responsive

## Notes
Created automatically by AI task creator.

## Created At
{created_at}
"""


def slugify(text):
    return (
        text.lower()
        .replace(" ", "_")
        .replace("-", "_")
    )


def create_task(title, priority, goal):
    filename = slugify(title) + ".md"

    path = PENDING_DIR / filename

    content = TEMPLATE.format(
        title=title,
        priority=priority,
        goal=goal,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    path.write_text(content, encoding="utf-8")

    print(f"Task created:")
    print(path)


def main():
    if len(sys.argv) < 4:
        print("Usage:")
        print('python AI_SYSTEM/create_task.py "Task Name" "High" "Goal"')
        return

    title = sys.argv[1]
    priority = sys.argv[2]
    goal = sys.argv[3]

    create_task(title, priority, goal)


if __name__ == "__main__":
    main()
