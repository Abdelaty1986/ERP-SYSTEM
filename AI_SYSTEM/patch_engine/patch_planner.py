from pathlib import Path
from datetime import datetime
import json
import sys

import sys
sys.path.append(str(Path(__file__).resolve().parent))
from patch_guard import guard_patch_plan

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PATCH_PLANS_DIR = PROJECT_ROOT / "AI_TASKS" / "patch_plans"
PENDING_DIR = PROJECT_ROOT / "AI_TASKS" / "pending"

PATCH_PLANS_DIR.mkdir(parents=True, exist_ok=True)

def get_latest_pending_task():
    tasks = sorted(PENDING_DIR.glob("*.md"))
    return tasks[0] if tasks else None

def build_plan(task_file, files):
    guard = guard_patch_plan(files)

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "REVIEW_ONLY",
        "task": task_file.name if task_file else None,
        "status": "SAFE_TO_REVIEW" if guard["safe"] else "BLOCKED_BY_GUARD",
        "files_requested": files,
        "guard": guard,
        "rules": [
            "Do not auto-apply patches.",
            "Do not modify database files.",
            "Do not modify accounting posting logic without manual review.",
            "Patch output is for review only.",
        ],
    }

def main():
    task = get_latest_pending_task()

    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        files = [
            "templates/developer_control.html",
            "templates/dev_ai_dashboard.html",
            "static/css/ledgerx_dev_system.css",
        ]

    plan = build_plan(task, files)

    out = PATCH_PLANS_DIR / f"patch_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Patch plan generated:")
    print(out)

    if not plan["guard"]["safe"]:
        print("BLOCKED_BY_GUARD")
        for item in plan["guard"]["blocked"]:
            print(f"- {item['file']}: {item['reason']}")
    else:
        print("SAFE_TO_REVIEW")

if __name__ == "__main__":
    main()
