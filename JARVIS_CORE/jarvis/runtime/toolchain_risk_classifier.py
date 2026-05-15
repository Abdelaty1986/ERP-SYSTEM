import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "toolchain_risk_classifier.json"
LOG_PATH = LOGS_DIR / "toolchain_risk_classifier.jsonl"

SOURCES = {
    "ide_awareness_runtime": MEMORY_DIR / "ide_awareness_runtime.json",
    "container_execution_awareness": MEMORY_DIR / "container_execution_awareness.json",
    "ci_cd_awareness_runtime": MEMORY_DIR / "ci_cd_awareness_runtime.json",
    "local_test_runner_observer": MEMORY_DIR / "local_test_runner_observer.json",
    "dependency_health_observer": MEMORY_DIR / "dependency_health_observer.json",
}


def load_json(path):
    if not path.exists():
        return {"exists": False, "data": None}
    try:
        return {"exists": True, "data": json.loads(path.read_text(encoding="utf-8"))}
    except Exception as exc:
        return {"exists": True, "data": None, "error": str(exc)}


class ToolchainRiskClassifier:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        sources = {name: load_json(path) for name, path in SOURCES.items()}
        available = [name for name, item in sources.items() if item.get("exists") and item.get("data") is not None]
        missing = [name for name, item in sources.items() if not item.get("exists")]
        unreadable = [name for name, item in sources.items() if item.get("exists") and item.get("data") is None]

        source_summaries = {}
        unsafe_sources = []
        watch_sources = []
        for name, item in sources.items():
            data = item.get("data") or {}
            safety_locked = (
                data.get("bounded") is True
                and data.get("execution_allowed") is False
                and data.get("apply_allowed") is False
                and data.get("autonomous_apply") is False
                and data.get("dangerous_autonomous_apply") is False
                and data.get("human_approval_required") is True
            )
            risk_signal = data.get("risk_signal", "unknown")
            if not safety_locked and data:
                unsafe_sources.append(name)
            if risk_signal == "watch":
                watch_sources.append(name)
            source_summaries[name] = {
                "available": item.get("exists") and data != {},
                "risk_signal": risk_signal,
                "safety_locked": safety_locked,
                "result": data.get("result"),
            }

        ci = (sources["ci_cd_awareness_runtime"].get("data") or {})
        deps = (sources["dependency_health_observer"].get("data") or {})
        tests = (sources["local_test_runner_observer"].get("data") or {})

        risk_reasons = []
        if ci.get("detected_path_count", 0) > 0:
            risk_reasons.append("deployment_or_ci_cd_files_detected")
        if deps.get("detected_file_count", 0) > 0 and not deps.get("lock_files_present"):
            risk_reasons.append("dependency_manifest_without_lock_file")
        if tests.get("python_test_file_count", 0) > 0:
            risk_reasons.append("local_tests_detected_but_not_executed")
        if unreadable:
            risk_reasons.append("unreadable_toolchain_sources")
        if unsafe_sources:
            risk_reasons.append("unsafe_runtime_lock_state_detected")

        if unsafe_sources or unreadable:
            risk_class = "high"
        elif watch_sources or risk_reasons:
            risk_class = "watch"
        else:
            risk_class = "low"

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "toolchain_risk_classifier",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "classifier_mode": "safe_read_only_toolchain_risk_aggregation",
            "phase": "phase_5_external_toolchain_runtime",
            "layer": "toolchain_risk_classifier",
            "available_source_count": len(available),
            "available_sources": available,
            "missing_sources": missing,
            "unreadable_sources": unreadable,
            "source_summaries": source_summaries,
            "watch_sources": watch_sources,
            "unsafe_sources": unsafe_sources,
            "risk_reasons": risk_reasons,
            "risk_class": risk_class,
            "monitoring_decision": {
                "safe_to_display_in_hud": not unreadable,
                "requires_human_review": risk_class in {"watch", "high"},
                "allow_tool_execution": False,
                "allow_destructive_execution": False,
                "allow_deploy": False,
            },
            "recommendation": "use_as_input_for_external_toolchain_hud",
            "result": "toolchain_risk_classifier_built",
        }

        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "risk_class": result["risk_class"],
            "watch_sources": result["watch_sources"],
            "unsafe_sources": result["unsafe_sources"],
            "execution_allowed": False,
            "apply_allowed": False,
            "human_approval_required": True,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(ToolchainRiskClassifier().build(), ensure_ascii=False, indent=2))
