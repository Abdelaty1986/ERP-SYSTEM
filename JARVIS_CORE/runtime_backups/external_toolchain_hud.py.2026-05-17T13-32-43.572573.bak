import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "external_toolchain_hud.json"
LOG_PATH = LOGS_DIR / "external_toolchain_hud.jsonl"

SOURCES = {
    "ide_awareness_runtime": MEMORY_DIR / "ide_awareness_runtime.json",
    "container_execution_awareness": MEMORY_DIR / "container_execution_awareness.json",
    "ci_cd_awareness_runtime": MEMORY_DIR / "ci_cd_awareness_runtime.json",
    "local_test_runner_observer": MEMORY_DIR / "local_test_runner_observer.json",
    "dependency_health_observer": MEMORY_DIR / "dependency_health_observer.json",
    "toolchain_risk_classifier": MEMORY_DIR / "toolchain_risk_classifier.json",
}


def load_json(path):
    if not path.exists():
        return {"exists": False, "data": None}
    try:
        return {"exists": True, "data": json.loads(path.read_text(encoding="utf-8"))}
    except Exception as exc:
        return {"exists": True, "data": None, "error": str(exc)}


class ExternalToolchainHud:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        sources = {name: load_json(path) for name, path in SOURCES.items()}
        available = [name for name, item in sources.items() if item.get("exists") and item.get("data") is not None]
        missing = [name for name, item in sources.items() if not item.get("exists")]
        unreadable = [name for name, item in sources.items() if item.get("exists") and item.get("data") is None]

        ide = sources["ide_awareness_runtime"].get("data") or {}
        container = sources["container_execution_awareness"].get("data") or {}
        ci = sources["ci_cd_awareness_runtime"].get("data") or {}
        tests = sources["local_test_runner_observer"].get("data") or {}
        deps = sources["dependency_health_observer"].get("data") or {}
        risk = sources["toolchain_risk_classifier"].get("data") or {}

        warnings = []
        for reason in risk.get("risk_reasons", []):
            warnings.append({"type": "toolchain_risk", "message": reason})
        if unreadable:
            warnings.append({"type": "source_read_error", "message": "One or more toolchain sources could not be read.", "sources": unreadable})

        hud = {
            "title": "External Toolchain Runtime",
            "phase": "Phase 5",
            "status": risk.get("risk_class", "unknown"),
            "monitoring_only": True,
            "requires_human_review": risk.get("monitoring_decision", {}).get("requires_human_review", True),
            "sections": {
                "ide_awareness": {
                    "state": ide.get("ide_awareness_state"),
                    "detected_indicators": ide.get("detected_indicators", []),
                },
                "container_awareness": {
                    "state": container.get("container_awareness_state"),
                    "detected_files": container.get("detected_files", []),
                },
                "ci_cd_awareness": {
                    "state": ci.get("ci_cd_awareness_state"),
                    "detected_paths": ci.get("detected_paths", []),
                    "workflow_file_count": ci.get("workflow_file_count"),
                },
                "local_test_runner": {
                    "state": tests.get("test_runner_state"),
                    "python_test_file_count": tests.get("python_test_file_count"),
                    "likely_test_runners": tests.get("likely_test_runners", []),
                },
                "dependency_health": {
                    "state": deps.get("dependency_health_state"),
                    "detected_files": deps.get("detected_files", []),
                    "lock_files_present": deps.get("lock_files_present", []),
                },
                "risk_classifier": {
                    "risk_class": risk.get("risk_class"),
                    "watch_sources": risk.get("watch_sources", []),
                    "unsafe_sources": risk.get("unsafe_sources", []),
                },
            },
            "warnings": warnings,
            "locks": {
                "execution_allowed": False,
                "apply_allowed": False,
                "autonomous_apply": False,
                "dangerous_autonomous_apply": False,
                "deploy_allowed": False,
                "destructive_execution_allowed": False,
                "human_approval_required": True,
            },
        }

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "external_toolchain_hud",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "hud_mode": "safe_read_only_external_toolchain_visibility",
            "phase": "phase_5_external_toolchain_runtime",
            "layer": "external_toolchain_hud",
            "available_source_count": len(available),
            "available_sources": available,
            "missing_sources": missing,
            "unreadable_sources": unreadable,
            "hud": hud,
            "learning_assessment": {
                "toolchain_state": "toolchain_monitoring_watch" if warnings else "toolchain_monitoring_stable",
                "safe_to_display_in_hud": not unreadable,
                "may_execute_recommendations": False,
                "may_apply_changes": False,
            },
            "recommendation": "phase_5_complete_continue_to_mobile_control_center",
            "result": "external_toolchain_hud_built",
        }

        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "toolchain_state": result["learning_assessment"]["toolchain_state"],
            "hud_status": result["hud"]["status"],
            "warning_count": len(result["hud"]["warnings"]),
            "execution_allowed": False,
            "apply_allowed": False,
            "human_approval_required": True,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(ExternalToolchainHud().build(), ensure_ascii=False, indent=2))
