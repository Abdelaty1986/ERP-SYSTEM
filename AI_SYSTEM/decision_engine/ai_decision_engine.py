from pathlib import Path
from datetime import datetime
import json

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DIFF_DIR = PROJECT_ROOT / "AI_TASKS" / "diff_reports"
TEST_DIR = PROJECT_ROOT / "AI_TASKS" / "test_plans"
PATCH_DIR = PROJECT_ROOT / "AI_TASKS" / "patch_plans"
DECISION_DIR = PROJECT_ROOT / "AI_TASKS" / "decisions"
PIPELINE_HISTORY = PROJECT_ROOT / "AI_SYSTEM" / "logs" / "pipeline_history.json"

DECISION_DIR.mkdir(parents=True, exist_ok=True)

def latest_json(folder):
    if not folder.exists():
        return None
    files = sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    try:
        return json.loads(files[0].read_text(encoding="utf-8"))
    except Exception:
        return None

def latest_pipeline():
    if not PIPELINE_HISTORY.exists():
        return None
    try:
        data = json.loads(PIPELINE_HISTORY.read_text(encoding="utf-8"))
        runs = data.get("runs", [])
        return runs[-1] if runs else None
    except Exception:
        return None

def make_decision():
    diff = latest_json(DIFF_DIR)
    test = latest_json(TEST_DIR)
    patch = latest_json(PATCH_DIR)
    pipeline = latest_pipeline()

    reasons = []
    decision = "SAFE_TO_CONTINUE"

    diff_risk = (diff or {}).get("overall_risk", "UNKNOWN")
    if diff_risk in ["HIGH", "UNKNOWN"]:
        decision = "NEEDS_REVIEW"
        reasons.append(f"Diff risk is {diff_risk}")

    if diff_risk == "HIGH":
        decision = "BLOCKED"
        reasons.append("High-risk changes detected")

    if test and test.get("manual_review_required"):
        decision = "NEEDS_REVIEW" if decision != "BLOCKED" else decision
        reasons.append("Test plan requires manual review")

    patch_status = (patch or {}).get("status")
    if patch_status == "BLOCKED_BY_GUARD":
        decision = "BLOCKED"
        reasons.append("Patch guard blocked requested files")

    pipeline_status = (pipeline or {}).get("status")
    if pipeline_status == "FAILED":
        decision = "NEEDS_REVIEW" if decision != "BLOCKED" else decision
        reasons.append("Latest pipeline run failed")

    if not reasons:
        reasons.append("No blocking or review conditions detected")

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision,
        "summary": {
            "diff_risk": diff_risk,
            "selected_tests": (test or {}).get("selected_tests", []),
            "patch_status": patch_status,
            "pipeline_status": pipeline_status,
        },
        "reasons": reasons,
        "policy": [
            "BLOCKED means do not merge or apply changes.",
            "NEEDS_REVIEW means manual review is required before merge.",
            "SAFE_TO_CONTINUE means continue development with normal validation.",
        ],
    }

def main():
    decision = make_decision()
    out = DECISION_DIR / f"decision_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(decision, indent=2, ensure_ascii=False), encoding="utf-8")

    print("AI decision generated:")
    print(out)
    print("Decision:", decision["decision"])

if __name__ == "__main__":
    main()
