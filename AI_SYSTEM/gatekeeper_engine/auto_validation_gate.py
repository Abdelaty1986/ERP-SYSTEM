from pathlib import Path
from datetime import datetime
import json

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DECISIONS_DIR = PROJECT_ROOT / "AI_TASKS" / "decisions"
SANDBOX_DIR = PROJECT_ROOT / "AI_TASKS" / "sandbox_results"
PATCH_DIR = PROJECT_ROOT / "AI_TASKS" / "patch_plans"
DIFF_DIR = PROJECT_ROOT / "AI_TASKS" / "diff_reports"

REPORTS_DIR = PROJECT_ROOT / "AI_TASKS" / "gate_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def latest_json(folder):
    if not folder.exists():
        return None

    files = sorted(
        folder.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not files:
        return None

    try:
        return json.loads(files[0].read_text(encoding="utf-8"))
    except Exception:
        return None


def main():
    decision = latest_json(DECISIONS_DIR) or {}
    sandbox = latest_json(SANDBOX_DIR) or {}
    patch = latest_json(PATCH_DIR) or {}
    diff = latest_json(DIFF_DIR) or {}

    final_status = "APPROVED_FOR_REVIEW"
    reasons = []

    if sandbox.get("status") != "PASSED":
        final_status = "REJECTED"
        reasons.append("Sandbox validation failed")

    if decision.get("decision") == "BLOCKED":
        final_status = "REJECTED"
        reasons.append("Decision engine blocked execution")

    if patch.get("status") == "BLOCKED_BY_GUARD":
        final_status = "REJECTED"
        reasons.append("Patch guard blocked requested files")

    if diff.get("overall_risk") == "HIGH":
        if final_status != "REJECTED":
            final_status = "REQUIRES_MANUAL_APPROVAL"
        reasons.append("High-risk diff detected")

    if decision.get("decision") == "NEEDS_REVIEW":
        if final_status != "REJECTED":
            final_status = "REQUIRES_MANUAL_APPROVAL"
        reasons.append("Decision engine requires review")

    if not reasons:
        reasons.append("All validation layers passed")

    report = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "gate_status": final_status,
        "decision_engine": decision.get("decision"),
        "sandbox_status": sandbox.get("status"),
        "patch_status": patch.get("status"),
        "diff_risk": diff.get("overall_risk"),
        "reasons": reasons,
        "policy": [
            "APPROVED_FOR_REVIEW does not mean auto-merge.",
            "Manual approval is still required before production merge.",
            "REJECTED means validation layers failed.",
        ]
    }

    out = REPORTS_DIR / f"gate_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("Auto validation gate report generated:")
    print(out)
    print("Gate Status:", final_status)


if __name__ == "__main__":
    main()
