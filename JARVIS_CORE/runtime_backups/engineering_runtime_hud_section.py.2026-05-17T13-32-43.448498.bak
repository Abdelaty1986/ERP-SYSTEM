import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "engineering_runtime_hud_section.json"
LOG_PATH = LOGS_DIR / "engineering_runtime_hud_section.jsonl"


def load_json(name):
    path = MEMORY_DIR / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class EngineeringRuntimeHudSection:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        approval = load_json("approval_gateway.json")
        controlled_apply = load_json("controlled_apply_decision.json")
        rollback = load_json("rollback_intelligence_layer.json")
        checkpoint = load_json("rollback_checkpoint_memory.json")
        supervision = load_json("execution_supervision_runtime.json")
        validation = load_json("project_apply_validation_guard.json")
        mutation = load_json("execution_journal.json")

        latest_session = approval.get("latest_session", {})
        apply_summary = controlled_apply.get("summary", {})
        checkpoint_summary = checkpoint.get("summary", {})

        locks = {
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "project_apply_allowed": False,
        }

        section = {
            "approval_state": latest_session.get("approval_state") or approval.get("gateway_state"),
            "authorization_scope": latest_session.get("authorization_scope"),
            "execution_lock_state": latest_session.get("execution_lock_state"),
            "apply_decision": apply_summary.get("apply_decision"),
            "controlled_apply_execution_allowed": apply_summary.get("execution_allowed", False),
            "rollback_ready": apply_summary.get("rollback_ready") or checkpoint_summary.get("rollback_ready") or rollback.get("rollback_state") == "rollback_ready",
            "rollback_state": rollback.get("rollback_state") or checkpoint_summary.get("checkpoint_state"),
            "mutation_state": mutation.get("summary", {}).get("lineage_state") or mutation.get("mode"),
            "validation_state": validation.get("state") or validation.get("result") or "not_available",
            "supervision_state": supervision.get("supervision_state"),
            "execution_decision": supervision.get("execution_decision"),
            "locks": locks,
        }

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "engineering_runtime_hud_section",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "hud_mode": "safe_read_only_engineering_runtime_section",
            "phase": "phase_6_full_mobile_control_center",
            "layer": "engineering_runtime_section",
            "section": section,
            "section_state": "locked" if section["locks"]["human_approval_required"] else "needs_review",
            "recommendation": "use_as_input_for_learning_runtime_hud_section",
            "result": "engineering_runtime_hud_section_built",
        }

        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def append_log(self, result):
        section = result["section"]
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "section_state": result["section_state"],
            "approval_state": section["approval_state"],
            "rollback_ready": section["rollback_ready"],
            "execution_allowed": False,
            "apply_allowed": False,
            "human_approval_required": True,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(EngineeringRuntimeHudSection().build(), ensure_ascii=False, indent=2))
