from pathlib import Path
from datetime import datetime
import json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PATCH_DIR = PROJECT_ROOT / "AI_TASKS" / "generated_patches"
TASKS_DIR = PROJECT_ROOT / "AI_TASKS" / "pending"

PATCH_DIR.mkdir(parents=True, exist_ok=True)

def latest_pending_task():
    tasks = sorted(TASKS_DIR.glob("*.md"))
    return tasks[0] if tasks else None

def main():
    task = latest_pending_task()
    task_name = task.stem if task else "no_task"

    patch = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "GENERATE_ONLY",
        "task": task.name if task else None,
        "status": "PATCH_DRAFT_READY",
        "target_files": [],
        "instructions": [
            "This is a generated patch draft only.",
            "Do not auto-apply to production files.",
            "Apply only inside sandbox after guard approval.",
            "Human approval is required before merging.",
        ],
        "patch_content": ""
    }

    out = PATCH_DIR / f"{task_name}_patch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(patch, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Patch draft generated:")
    print(out)

if __name__ == "__main__":
    main()
