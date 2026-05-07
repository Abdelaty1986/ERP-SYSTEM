from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent

TASKS = {
    "pending": ROOT / "AI_TASKS" / "pending",
    "in_progress": ROOT / "AI_TASKS" / "in_progress",
    "completed": ROOT / "AI_TASKS" / "completed",
    "blocked": ROOT / "AI_TASKS" / "blocked",
}


def move_task(task_name, source, target):
    src = TASKS[source] / task_name
    dst = TASKS[target] / task_name

    if not src.exists():
        print(f"Task not found: {src}")
        return

    shutil.move(str(src), str(dst))
    print(f"Moved: {task_name}")
    print(f"{source} -> {target}")


def list_tasks():
    print("\\n=== TASK STATUS ===\\n")

    for status, folder in TASKS.items():
        print(f"[{status.upper()}]")

        tasks = list(folder.glob("*.md"))

        if not tasks:
            print("  - none")

        for task in tasks:
            print(f"  - {task.name}")

        print()


def main():
    list_tasks()

    print("Usage Example:")
    print("move_task('task.md', 'pending', 'in_progress')")


if __name__ == "__main__":
    main()
