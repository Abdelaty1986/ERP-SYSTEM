import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "toolchain_runtime_hud_section.json"
LOG_PATH = LOGS_DIR / "toolchain_runtime_hud_section.jsonl"


def load_json(name):
    path = MEMORY_DIR / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class ToolchainRuntimeHudSection:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        ide = load_json("ide_awareness_runtime.json")
        container = load_json("container_execution_awareness.json")
        ci = load_json("ci_cd_awareness_runtime.json")
        tests = load_json("local_test_runner_observer.json")
        deps = load_json("dependency_health_observer.json")
        risk = load_json("toolchain_risk_classifier.json")
        hud = load_json("external_toolchain_hud.json")

        section = {
            "ide_state": ide.get("ide_awareness_state"),
            "container_state": container.get("container_awareness_state"),
            "container_files": container.get("detected_files", []),
            "ci_cd_state": ci.get("ci_cd_awareness_state"),
            "ci_cd_detected_paths": ci.get("detected_paths", []),
            "test_runner_state": tests.get("test_runner_state"),
            "python_test_file_count": tests.get("python_test_file_count"),
            "dependency_state": deps.get("dependency_health_state"),
            "dependency_files": deps.get("detected_files", []),
            "lock_files_present": deps.get("lock_files_present", []),
            "risk_class": risk.get("risk_class"),
            "risk_reasons": risk.get("risk_reasons", []),
            "watch_sources": risk.get("watch_sources", []),
            "unsafe_sources": risk.get("unsafe_sources", []),
            "external_toolchain_hud_status": hud.get("hud", {}).get("status"),
            "external_toolchain_warnings": hud.get("hud", {}).get("warnings", []),
        }

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "toolchain_runtime_hud_section",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "hud_mode": "safe_read_only_toolchain_runtime_section",
            "phase": "phase_6_full_mobile_control_center",
            "layer": "toolchain_runtime_section",
            "section": section,
            "warning_count": len(section["risk_reasons"]) + len(section["external_toolchain_warnings"]),
            "section_state": section["risk_class"] or "unknown",
            "recommendation": "use_as_input_for_runtime_warnings_locks_hud_section",
            "result": "toolchain_runtime_hud_section_built",
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
    print(json.dumps(ToolchainRuntimeHudSection().build(), ensure_ascii=False, indent=2))
