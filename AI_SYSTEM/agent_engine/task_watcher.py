from pathlib import Path
from datetime import datetime
import json
import subprocess
import time

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PENDING_DIR = PROJECT_ROOT / "AI_TASKS" / "pending"
LOG_DIR = PROJECT_ROOT / "AI_TASKS" / "agent_logs"
STATE_FILE = LOG_DIR / "watcher_state.json"

LOG_DIR.mkdir(parents=True, exist_ok=True)

COMMANDS = [
    ("Full Pipeline", "python AI_SYSTEM/pipelines/AI_DEV_PIPELINE.py --full"),
    ("Generate Structured Patch", "python AI_SYSTEM/patch_engine/patch_generator.py"),
    ("Sandbox Patch Apply", "python AI_SYSTEM/sandbox_engine/sandbox_patch_applier.py"),
    ("Auto Validation Gate", "python AI_SYSTEM/gatekeeper_engine/auto_validation_gate.py"),
]


def load_state():
    if not STATE_FILE.exists():
        return {"processed": []}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"processed": []}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def run_command(title, command):
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        shell=True,
        capture_output=True,
        text=True,
        timeout=600,
    )

    return {
        "title": title,
        "command": command,
        "returncode": result.returncode,
        "ok": result.returncode == 0,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }


def process_task(task_file):
    steps = []

    for title, command in COMMANDS:
        step = run_command(title, command)
        steps.append(step)
        if not step["ok"]:
            break

    status = "WAITING_FOR_APPROVAL" if all(s["ok"] for s in steps) else "FAILED"

    report = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "task": task_file.name,
        "status": status,
        "steps": steps,
        "next_action": (
            "Review gate/apply reports, then approve manually if safe."
            if status == "WAITING_FOR_APPROVAL"
            else "Review failed step logs."
        ),
    }

    out = LOG_DIR / f"agent_run_{task_file.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if status == "WAITING_FOR_APPROVAL":
        notify = run_command(
            "Approval Notification",
            "python AI_SYSTEM/notification_engine/approval_notifier.py"
        )
        report["notification"] = notify
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Agent run report:")
    print(out)
    print("Status:", status)

    return report


def scan_once():
    state = load_state()
    processed = set(state.get("processed", []))

    tasks = sorted(PENDING_DIR.glob("*.md")) if PENDING_DIR.exists() else []

    new_tasks = [t for t in tasks if t.name not in processed]

    if not new_tasks:
        print("No new pending tasks.")
        return False

    for task in new_tasks:
        report = process_task(task)
        processed.add(task.name)

        state["processed"] = sorted(processed)
        state["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state["last_task"] = task.name
        state["last_status"] = report["status"]
        save_state(state)

    return True


def watch_loop(interval=60):
    print("LedgerX AI Task Watcher started.")
    print("Press CTRL+C to stop.")
    while True:
        scan_once()
        time.sleep(interval)


def main():
    import sys

    if "--watch" in sys.argv:
        watch_loop()
    else:
        scan_once()


if __name__ == "__main__":
    main()
