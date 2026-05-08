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


def build_sample_safe_patch(task):
    """
    Generates a real structured patch draft.
    This is intentionally conservative:
    - targets AI Dashboard only
    - does not touch accounting logic
    - requires exact old_text match before applying
    """

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "STRUCTURED_PATCH_REVIEW_ONLY",
        "task": task.name if task else None,
        "status": "PATCH_DRAFT_READY",
        "target_files": [
            "templates/dev_ai_dashboard.html"
        ],
        "operations": [
            {
                "type": "replace_text",
                "file": "templates/dev_ai_dashboard.html",
                "old_text": "مركز متابعة القرار الذكي، تحليل الفروقات، خطة الاختبارات، وحالة الـ Pipeline داخل LedgerX.",
                "new_text": "مركز متابعة القرار الذكي، تحليل الفروقات، خطة الاختبارات، حالة الـ Pipeline، ونتائج بوابة الاعتماد داخل LedgerX."
            }
        ],
        "instructions": [
            "Patch is structured and review-only.",
            "Apply only after Patch Guard approval.",
            "Apply inside sandbox first.",
            "Human approval is required before production apply.",
            "Exact old_text match is required."
        ]
    }


def main():
    task = latest_pending_task()
    task_name = task.stem if task else "no_task"

    patch = build_sample_safe_patch(task)

    out = PATCH_DIR / f"{task_name}_patch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(patch, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Structured patch draft generated:")
    print(out)


if __name__ == "__main__":
    main()
