import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "mobile_control_center_hud_integration.json"
LOG_PATH = LOGS_DIR / "mobile_control_center_hud_integration.jsonl"

SECTION_FILES = {
    "unified": "unified_runtime_hud_api.json",
    "cognitive": "cognitive_supervision_hud_section.json",
    "agent_society": "agent_society_hud_section.json",
    "engineering": "engineering_runtime_hud_section.json",
    "learning": "learning_runtime_hud_section.json",
    "toolchain": "toolchain_runtime_hud_section.json",
    "warnings_locks": "runtime_warnings_locks_hud_section.json",
}


def load_json(name):
    path = MEMORY_DIR / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _get_actual_mode():
    try:
        from jarvis.runtime.execution_mode_manager import read_mode
        return read_mode().get("mode", "controlled_real_execution")
    except Exception:
        return "controlled_real_execution"


def build_mobile_control_center_hud(write_output=True):
    sections = {name: load_json(filename) for name, filename in SECTION_FILES.items()}
    warnings_locks = sections.get("warnings_locks", {})

    current_mode = _get_actual_mode()
    is_simulation = current_mode == "simulation_only"

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "runtime": "mobile_control_center_hud_integration",
        "bounded": True,
        "execution_allowed": not is_simulation,
        "apply_allowed": not is_simulation,
        "autonomous_apply": False,
        "dangerous_autonomous_apply": False,
        "human_approval_required": current_mode == "supervised_real_execution",
        "hud_mode": current_mode,
        "phase": "phase_6_full_mobile_control_center",
        "layer": "mobile_control_center_ui_integration",
        "mobile_hud": {
            "status": warnings_locks.get("section_state", "unknown"),
            "human_review_required": warnings_locks.get("human_review_required", True),
            "section_states": {
                "cognitive": sections.get("cognitive", {}).get("section_state"),
                "agent_society": sections.get("agent_society", {}).get("section_state"),
                "engineering": sections.get("engineering", {}).get("section_state"),
                "learning": sections.get("learning", {}).get("section_state"),
                "toolchain": sections.get("toolchain", {}).get("section_state"),
                "warnings_locks": warnings_locks.get("section_state"),
            },
            "sections": sections,
            "locks": warnings_locks.get("locks", {
                "execution_allowed": False,
                "apply_allowed": False,
                "autonomous_apply": False,
                "dangerous_autonomous_apply": False,
                "human_approval_required": True,
            }),
            "warnings": warnings_locks.get("warnings", []),
            "blockers": warnings_locks.get("blockers", []),
        },
        "recommendation": "phase_6_complete_continue_to_voice_runtime",
        "result": "mobile_control_center_hud_integration_built",
    }

    if write_output:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "timestamp": result["timestamp"],
                "runtime": result["runtime"],
                "status": result["mobile_hud"]["status"],
                "human_review_required": result["mobile_hud"]["human_review_required"],
                "execution_allowed": result["execution_allowed"],
                "apply_allowed": result["apply_allowed"],
                "human_approval_required": result["human_approval_required"],
            }, ensure_ascii=False) + "\n")

    return result


if __name__ == "__main__":
    print(json.dumps(build_mobile_control_center_hud(), ensure_ascii=False, indent=2))
