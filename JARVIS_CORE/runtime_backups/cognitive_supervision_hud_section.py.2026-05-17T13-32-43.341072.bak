import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "cognitive_supervision_hud_section.json"
LOG_PATH = LOGS_DIR / "cognitive_supervision_hud_section.jsonl"


def load_json(name):
    path = MEMORY_DIR / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class CognitiveSupervisionHudSection:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        hud = load_json("runtime_self_monitoring_hud.json")
        supervision = hud.get("cognitive_supervision", {})

        section = {
            "health_state": supervision.get("health_state", "unknown"),
            "silence_state": supervision.get("silence_state", "unknown"),
            "stability_state": supervision.get("stability_state", "unknown"),
            "reflection_state": supervision.get("reflection_state", "unknown"),
            "next_runtime_allowed": supervision.get("next_runtime_allowed", False),
            "health_score": supervision.get("health_score"),
            "stability_score": supervision.get("stability_score"),
            "loop_state": supervision.get("loop_state"),
        }

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "cognitive_supervision_hud_section",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "hud_mode": "safe_read_only_cognitive_supervision_section",
            "phase": "phase_6_full_mobile_control_center",
            "layer": "cognitive_supervision_section",
            "source": "runtime_self_monitoring_hud.json",
            "section": section,
            "section_state": "stable" if all([
                section["health_state"] == "stable",
                section["silence_state"] == "active",
                section["stability_state"] == "stable",
                section["reflection_state"] == "clear",
                section["next_runtime_allowed"] is True,
            ]) else "watch",
            "recommendation": "use_as_input_for_agent_society_hud_section",
            "result": "cognitive_supervision_hud_section_built",
        }
        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "section_state": result["section_state"],
            "next_runtime_allowed": result["section"]["next_runtime_allowed"],
            "execution_allowed": False,
            "apply_allowed": False,
            "human_approval_required": True,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(CognitiveSupervisionHudSection().build(), ensure_ascii=False, indent=2))
