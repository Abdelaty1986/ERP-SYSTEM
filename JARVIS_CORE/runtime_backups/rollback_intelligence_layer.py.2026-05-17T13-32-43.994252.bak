import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"

SUPERVISION_PATH = MEMORY_DIR / "execution_supervision_runtime.json"
ROLLBACK_MEMORY_PATH = MEMORY_DIR / "rollback_checkpoint_memory.json"
ROLLBACK_INTELLIGENCE_PATH = MEMORY_DIR / "rollback_intelligence_layer.json"


def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class RollbackIntelligenceLayer:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def analyze(self):
        supervision = load_json(SUPERVISION_PATH)
        rollback_memory = load_json(ROLLBACK_MEMORY_PATH)

        checkpoint_available = bool(rollback_memory)
        rollback_required = supervision.get("execution_controls", {}).get(
            "rollback_checkpoint_required",
            True,
        )

        rollback_state = (
            "rollback_ready"
            if checkpoint_available and rollback_required
            else "rollback_required_but_checkpoint_missing"
            if rollback_required
            else "rollback_not_required"
        )

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "rollback_intelligence_layer",
            "bounded": True,
            "dangerous_autonomous_apply": False,
            "rollback_mode": "safe_read_only_rollback_analysis",
            "checkpoint_available": checkpoint_available,
            "rollback_required": rollback_required,
            "rollback_state": rollback_state,
            "execution_supervision_state": supervision.get("supervision_state"),
            "rollback_decision": (
                "allow_guarded_planning_only"
                if rollback_state == "rollback_ready"
                else "block_execution_until_checkpoint"
            ),
            "guardrails": {
                "rollback_required_before_apply": True,
                "human_review_required": True,
                "autonomous_apply_allowed": False,
            },
            "result": "rollback_intelligence_built",
        }

        ROLLBACK_INTELLIGENCE_PATH.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return result


if __name__ == "__main__":
    result = RollbackIntelligenceLayer().analyze()
    print(json.dumps(result, ensure_ascii=False, indent=2))
