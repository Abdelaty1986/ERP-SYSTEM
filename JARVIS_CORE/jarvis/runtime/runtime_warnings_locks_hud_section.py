import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "runtime_warnings_locks_hud_section.json"
LOG_PATH = LOGS_DIR / "runtime_warnings_locks_hud_section.jsonl"

SECTION_FILES = {
    "cognitive": "cognitive_supervision_hud_section.json",
    "agent_society": "agent_society_hud_section.json",
    "engineering": "engineering_runtime_hud_section.json",
    "learning": "learning_runtime_hud_section.json",
    "toolchain": "toolchain_runtime_hud_section.json",
}


def load_json(name):
    path = MEMORY_DIR / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class RuntimeWarningsLocksHudSection:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        sections = {name: load_json(filename) for name, filename in SECTION_FILES.items()}
        warnings = []
        blockers = []
        watch_states = []

        for name, data in sections.items():
            state = data.get("section_state")
            if state in {"watch", "high", "needs_review"}:
                watch_states.append({"section": name, "state": state})
            if data.get("warning_count"):
                warnings.append({
                    "section": name,
                    "warning_count": data.get("warning_count"),
                    "state": state,
                })

        engineering = sections.get("engineering", {}).get("section", {})
        learning = sections.get("learning", {}).get("section", {})
        toolchain = sections.get("toolchain", {}).get("section", {})

        if engineering.get("validation_state") == "not_available":
            blockers.append({"section": "engineering", "reason": "validation_guard_not_available"})
        for item in learning.get("review_items", []):
            blockers.append({"section": "learning", "reason": item.get("reason"), "subject": item.get("provider")})
        for reason in toolchain.get("risk_reasons", []):
            blockers.append({"section": "toolchain", "reason": reason})

        locks = {
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "auto_apply_enabled": False,
            "deploy_allowed": False,
            "destructive_execution_allowed": False,
        }

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "runtime_warnings_locks_hud_section",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "hud_mode": "safe_read_only_warnings_locks_section",
            "phase": "phase_6_full_mobile_control_center",
            "layer": "runtime_warnings_locks_section",
            "watch_states": watch_states,
            "warnings": warnings,
            "blockers": blockers,
            "locks": locks,
            "human_review_required": True if blockers or watch_states else False,
            "section_state": "watch" if blockers or watch_states else "stable",
            "recommendation": "use_as_input_for_mobile_control_center_ui_integration",
            "result": "runtime_warnings_locks_hud_section_built",
        }

        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "section_state": result["section_state"],
            "warning_count": len(result["warnings"]),
            "blocker_count": len(result["blockers"]),
            "human_review_required": result["human_review_required"],
            "execution_allowed": False,
            "apply_allowed": False,
            "human_approval_required": True,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(RuntimeWarningsLocksHudSection().build(), ensure_ascii=False, indent=2))
