import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "learning_runtime_hud_section.json"
LOG_PATH = LOGS_DIR / "learning_runtime_hud_section.jsonl"


def load_json(name):
    path = MEMORY_DIR / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class LearningRuntimeHudSection:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        summary = load_json("runtime_learning_summary.json")
        providers = load_json("provider_scoring_memory.json")
        routing = load_json("adaptive_routing_recommendations.json")
        stability = load_json("learning_stability_monitor.json")
        safe_hud = load_json("safe_learning_hud_report.json")

        section = {
            "runtime_learning_state": summary.get("learning_assessment", {}).get("learning_state"),
            "review_items": summary.get("review_items", []),
            "provider_scoring_state": providers.get("learning_assessment", {}).get("learning_state"),
            "recommended_provider_for_review": providers.get("recommended_provider_for_review"),
            "provider_review_flags": providers.get("review_flags", []),
            "adaptive_routing_state": routing.get("learning_assessment", {}).get("learning_state"),
            "provider_decision_state": routing.get("recommendations", {}).get("provider", {}).get("decision_state"),
            "learning_stability": stability.get("learning_stability"),
            "safety_stability": stability.get("safety_stability"),
            "next_runtime_allowed": stability.get("monitor_decision", {}).get("next_runtime_allowed", False),
            "safe_learning_hud_status": safe_hud.get("hud", {}).get("status"),
            "safe_learning_warnings": safe_hud.get("hud", {}).get("warnings", []),
        }
        warning_count = len(section["review_items"]) + len(section["provider_review_flags"]) + len(section["safe_learning_warnings"])

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "learning_runtime_hud_section",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "hud_mode": "safe_read_only_learning_runtime_section",
            "phase": "phase_6_full_mobile_control_center",
            "layer": "learning_runtime_section",
            "section": section,
            "warning_count": warning_count,
            "section_state": "watch" if warning_count else "stable",
            "recommendation": "use_as_input_for_toolchain_runtime_hud_section",
            "result": "learning_runtime_hud_section_built",
        }
        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "section_state": result["section_state"],
            "warning_count": result["warning_count"],
            "execution_allowed": False,
            "apply_allowed": False,
            "human_approval_required": True,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(LearningRuntimeHudSection().build(), ensure_ascii=False, indent=2))
