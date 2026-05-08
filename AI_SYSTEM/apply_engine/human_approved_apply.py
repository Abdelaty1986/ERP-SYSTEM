from pathlib import Path
from datetime import datetime
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]

GATE_DIR = PROJECT_ROOT / "AI_TASKS" / "gate_reports"
PATCH_DIR = PROJECT_ROOT / "AI_TASKS" / "generated_patches"
REPORTS_DIR = PROJECT_ROOT / "AI_TASKS" / "apply_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def latest_json(folder):
    if not folder.exists():
        return None, None

    files = sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not files:
        return None, None

    latest = files[0]

    try:
        return latest, json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return latest, None


def apply_operation(operation):
    if operation.get("type") != "replace_text":
        return False, f"Unsupported operation type: {operation.get('type')}"

    rel_file = operation.get("file")
    old_text = operation.get("old_text", "")
    new_text = operation.get("new_text", "")

    target = PROJECT_ROOT / rel_file

    if not target.exists():
        return False, f"Target file not found: {rel_file}"

    content = target.read_text(encoding="utf-8")

    if old_text not in content:
        if new_text and new_text in content:
            return True, f"Already applied in production file: {rel_file}"
        return False, f"old_text not found in production file: {rel_file}"

    target.write_text(content.replace(old_text, new_text, 1), encoding="utf-8")
    return True, f"Applied replace_text to {rel_file}"


def write_report(status, reasons, patch_file=None, gate_file=None, applied=None, failed=None):
    report = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "apply_status": status,
        "patch_file": str(patch_file) if patch_file else None,
        "gate_file": str(gate_file) if gate_file else None,
        "applied": applied or [],
        "failed": failed or [],
        "reasons": reasons,
        "policy": [
            "No patch can be applied without --approve.",
            "Gate status must be APPROVED_FOR_REVIEW.",
            "Patch must contain structured operations.",
            "Exact old_text match is required.",
        ],
    }

    out = REPORTS_DIR / f"apply_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Apply report generated:")
    print(out)
    print("Apply Status:", status)


def main():
    approved = "--approve" in sys.argv

    gate_file, gate = latest_json(GATE_DIR)
    patch_file, patch = latest_json(PATCH_DIR)

    reasons = []

    if not approved:
        reasons.append("Missing explicit --approve flag.")
        write_report("WAITING_FOR_HUMAN_APPROVAL", reasons, patch_file, gate_file)
        return False

    if not gate:
        reasons.append("No gate report found.")
        write_report("REJECTED", reasons, patch_file, gate_file)
        return False

    if gate.get("gate_status") != "APPROVED_FOR_REVIEW":
        reasons.append(f"Gate status is not approved: {gate.get('gate_status')}")
        write_report("REJECTED", reasons, patch_file, gate_file)
        return False

    if not patch:
        reasons.append("No generated patch found.")
        write_report("REJECTED", reasons, patch_file, gate_file)
        return False

    operations = patch.get("operations") or []

    if not operations:
        reasons.append("Patch contains no structured operations.")
        write_report("REJECTED_EMPTY_PATCH", reasons, patch_file, gate_file)
        return False

    applied = []
    failed = []

    for operation in operations:
        ok, message = apply_operation(operation)
        item = {"operation": operation, "ok": ok, "message": message}
        if ok:
            applied.append(item)
        else:
            failed.append(item)

    if failed:
        reasons.append("One or more operations failed. Partial apply may require review.")
        write_report("FAILED", reasons, patch_file, gate_file, applied, failed)
        return False

    reasons.append("Patch applied after explicit human approval and approved gate.")
    write_report("APPLIED", reasons, patch_file, gate_file, applied, failed)
    return True


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
