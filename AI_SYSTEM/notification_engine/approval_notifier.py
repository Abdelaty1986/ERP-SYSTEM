from pathlib import Path
from datetime import datetime
import json

PROJECT_ROOT = Path(__file__).resolve().parents[2]

AGENT_LOGS = PROJECT_ROOT / "AI_TASKS" / "agent_logs"
GATE_REPORTS = PROJECT_ROOT / "AI_TASKS" / "gate_reports"
PATCHES = PROJECT_ROOT / "AI_TASKS" / "generated_patches"
NOTIFICATIONS = PROJECT_ROOT / "AI_TASKS" / "notifications"

NOTIFICATIONS.mkdir(parents=True, exist_ok=True)


def latest_json(folder, pattern="*.json"):
    if not folder.exists():
        return None, None

    files = sorted(folder.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)

    if not files:
        return None, None

    f = files[0]

    try:
        return f, json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return f, None


def main():
    agent_file, agent = latest_json(AGENT_LOGS, "agent_run_*.json")
    gate_file, gate = latest_json(GATE_REPORTS)
    patch_file, patch = latest_json(PATCHES)

    if not agent:
        print("No agent run found.")
        return

    status = agent.get("status")

    if status != "WAITING_FOR_APPROVAL":
        print("No approval needed.")
        return

    operations = patch.get("operations", []) if patch else []

    notification = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": "APPROVAL_REQUIRED",
        "task": agent.get("task"),
        "agent_status": status,
        "gate_status": gate.get("gate_status") if gate else None,
        "patch_file": str(patch_file) if patch_file else None,
        "gate_file": str(gate_file) if gate_file else None,
        "agent_file": str(agent_file) if agent_file else None,
        "operations_count": len(operations),
        "target_files": [op.get("file") for op in operations],
        "message": "LedgerX AI has a patch ready. Review and approve if safe.",
        "approve_command": "python AI_SYSTEM/apply_engine/human_approved_apply.py --approve",
        "reject_action": "Do nothing, or move task to blocked.",
    }

    out = NOTIFICATIONS / f"approval_required_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(notification, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Approval notification generated:")
    print(out)
    print("APPROVAL_REQUIRED")


if __name__ == "__main__":
    main()
