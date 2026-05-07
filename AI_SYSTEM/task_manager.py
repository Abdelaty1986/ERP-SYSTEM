from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent

TASK_ROOT = ROOT / "AI_TASKS"

STATUSES = [
    "pending",
    "in_progress",
    "completed",
    "blocked"
]


def list_tasks():
    print("\n=== TASK STATUS ===\n")

    for status in STATUSES:
        folder = TASK_ROOT / status

        print(f"[{status.upper()}]")

        tasks = list(folder.glob("*.md"))

        if not tasks:
            print("  - none")
        else:
            for task in tasks:
                print(f"  - {task.name}")

        print()


def move_task(task_name, source, target):
    source_path = TASK_ROOT / source / task_name
    target_path = TASK_ROOT / target / task_name

    if not source_path.exists():
        print(f"Task not found: {source_path}")
        return

    shutil.move(str(source_path), str(target_path))

    print(f"Moved: {task_name}")
    print(f"{source} -> {target}")


def main():
    if len(sys.argv) == 1:
        list_tasks()
        return

    command = sys.argv[1]

    if command == "move":
        if len(sys.argv) != 5:
            print("Usage:")
            print("python AI_SYSTEM/task_manager.py move task.md pending completed")
            return

        task_name = sys.argv[2]
        source = sys.argv[3]
        target = sys.argv[4]

        move_task(task_name, source, target)
        return

    print("Unknown command")


if __name__ == "__main__":
    main()
