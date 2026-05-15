import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "unified_runtime_hud_api.json"
LOG_PATH = LOGS_DIR / "unified_runtime_hud_api.jsonl"

SOURCES = {
    "engineering": [
        "approval_gateway.json",
        "controlled_apply_decision.json",
        "rollback_intelligence_layer.json",
        "rollback_checkpoint_memory.json",
        "execution_supervision_runtime.json",
        "project_apply_validation_guard.json",
        "execution_journal.json",
    ],
    "agent_society": [
        "agent_society_registry.json",
        "agent_society_routing.json",
        "agent_society_delegation.json",
        "agent_society_consensus.json",
        "agent_society_event_summary.json",
        "agent_society_aggregate_state.json",
    ],
    "cognition": [
        "runtime_self_monitoring_hud.json",
        "cognition_health_report.json",
        "runtime_silence_detection.json",
        "cognitive_stability_analysis.json",
        "cognitive_reflection_runtime.json",
        "long_running_runtime_loop.json",
    ],
    "learning": [
        "runtime_learning_summary.json",
        "provider_scoring_memory.json",
        "adaptive_routing_recommendations.json",
        "learning_stability_monitor.json",
        "safe_learning_hud_report.json",
    ],
    "toolchain": [
        "ide_awareness_runtime.json",
        "container_execution_awareness.json",
        "ci_cd_awareness_runtime.json",
        "local_test_runner_observer.json",
        "dependency_health_observer.json",
        "toolchain_risk_classifier.json",
        "external_toolchain_hud.json",
    ],
}


def load_json(path):
    if not path.exists():
        return {"exists": False, "data": None}
    try:
        return {"exists": True, "data": json.loads(path.read_text(encoding="utf-8"))}
    except Exception as exc:
        return {"exists": True, "data": None, "error": str(exc)}


class UnifiedRuntimeHudApi:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        sections = {}
        available_sources = []
        missing_sources = []
        unreadable_sources = []

        for section, filenames in SOURCES.items():
            section_sources = {}
            for filename in filenames:
                source_name = filename.replace(".json", "")
                payload = load_json(MEMORY_DIR / filename)
                section_sources[source_name] = payload
                if payload.get("exists") and payload.get("data") is not None:
                    available_sources.append(source_name)
                elif not payload.get("exists"):
                    missing_sources.append(source_name)
                else:
                    unreadable_sources.append(source_name)
            sections[section] = {
                "available_count": sum(
                    1 for payload in section_sources.values()
                    if payload.get("exists") and payload.get("data") is not None
                ),
                "sources": section_sources,
            }

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "unified_runtime_hud_api",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "api_mode": "safe_read_only_runtime_hud_aggregation",
            "phase": "phase_6_full_mobile_control_center",
            "layer": "unified_runtime_hud_api",
            "source_policy": "runtime_memory_only",
            "available_source_count": len(available_sources),
            "available_sources": available_sources,
            "missing_sources": missing_sources,
            "unreadable_sources": unreadable_sources,
            "sections": sections,
            "summary": {
                "engineering_available": sections["engineering"]["available_count"],
                "agent_society_available": sections["agent_society"]["available_count"],
                "cognition_available": sections["cognition"]["available_count"],
                "learning_available": sections["learning"]["available_count"],
                "toolchain_available": sections["toolchain"]["available_count"],
                "safe_to_display": not unreadable_sources,
            },
            "recommendation": "use_as_input_for_cognitive_supervision_hud_section",
            "result": "unified_runtime_hud_api_built",
        }

        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "available_source_count": result["available_source_count"],
            "safe_to_display": result["summary"]["safe_to_display"],
            "execution_allowed": False,
            "apply_allowed": False,
            "human_approval_required": True,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(UnifiedRuntimeHudApi().build(), ensure_ascii=False, indent=2))
