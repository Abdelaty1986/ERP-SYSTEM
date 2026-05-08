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


def write_report(status, reasons, patch_file=None, gate_file=None):
    report = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "apply_status": status,
        "patch_file": str(patch_file) if patch_file else None,
        "gate_file": str(gate_file) if gate_file else None,
        "reasons": reasons,
        "policy": [
            "No patch can be applied without --approve.",
            "Gate status must be APPROVED_FOR_REVIEW.",
            "Patch must contain explicit patch_content.",
            "This engine must never apply empty or unsafe patches.",
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

    patch_content = (patch.get("patch_content") or "").strip()

    if not patch_content:
        reasons.append("Patch content is empty. Nothing can be applied safely.")
        write_report("REJECTED_EMPTY_PATCH", reasons, patch_file, gate_file)
        return False

    reasons.append("Patch content exists, but automatic code application is not enabled yet.")
    reasons.append("Next phase should implement controlled unified-diff apply inside sandbox first.")

    write_report("READY_BUT_NOT_APPLIED", reasons, patch_file, gate_file)
    return False


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
