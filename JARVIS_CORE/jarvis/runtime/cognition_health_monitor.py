import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_MEMORY = PROJECT_ROOT / "JARVIS_CORE" / "runtime_memory"
RUNTIME_LOGS = PROJECT_ROOT / "JARVIS_CORE" / "runtime_logs"

SAFETY_CONTRACT = {
    "bounded": True,
    "analysis_only": True,
    "execution_allowed": False,
    "apply_allowed": False,
    "autonomous_apply": False,
    "database_mutation_allowed": False,
    "deploy_allowed": False,
    "human_approval_required": True,
}

OUTPUTS = {
    "cognitive_health": RUNTIME_MEMORY / "cognitive_health_state.json",
    "self_evaluation": RUNTIME_MEMORY / "self_evaluation_report.json",
    "decision_quality": RUNTIME_MEMORY / "decision_quality_analysis.json",
    "cognitive_drift": RUNTIME_MEMORY / "cognitive_drift_report.json",
    "self_improvement": RUNTIME_MEMORY / "self_improvement_plan.json",
    "meta_cognition": RUNTIME_MEMORY / "meta_cognition_state.json",
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _safe_read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _safe_load_json(path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def _load_jsonl(path, limit=500):
    rows = []
    text = _safe_read_text(path)
    if not text:
        return rows
    for line in text.splitlines()[-limit:]:
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append({"raw": line, "parse_error": True})
    return rows


def _write_json(path, payload):
    RUNTIME_MEMORY.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _runtime_memory_files():
    if not RUNTIME_MEMORY.exists():
        return []
    return sorted(path for path in RUNTIME_MEMORY.iterdir() if path.is_file())


def _runtime_log_files():
    if not RUNTIME_LOGS.exists():
        return []
    return sorted(path for path in RUNTIME_LOGS.iterdir() if path.is_file())


def _json_validity(files):
    valid = 0
    invalid = []
    json_files = [path for path in files if path.suffix == ".json"]
    for path in json_files:
        if _safe_load_json(path) is None:
            invalid.append(path.name)
        else:
            valid += 1
    return {
        "json_files": len(json_files),
        "valid_json": valid,
        "invalid_json": invalid,
    }


def _line_repetition_score(paths):
    counter = Counter()
    total = 0
    for path in paths:
        text = _safe_read_text(path)
        for line in text.splitlines():
            normalized = line.strip()
            if not normalized:
                continue
            counter[normalized] += 1
            total += 1
    repeated = sum(count - 1 for count in counter.values() if count > 1)
    return round(repeated / total, 4) if total else 0.0


def _collect_signals():
    memory_files = _runtime_memory_files()
    log_files = _runtime_log_files()
    text_pool = "\n".join(_safe_read_text(path) for path in memory_files + log_files)
    lowered = text_pool.lower()
    signals = {
        "memory_file_count": len(memory_files),
        "log_file_count": len(log_files),
        "json_validity": _json_validity(memory_files + log_files),
        "warning_terms": lowered.count("warning"),
        "critical_terms": lowered.count("critical"),
        "error_terms": lowered.count("error"),
        "approval_terms": lowered.count("approval"),
        "human_terms": lowered.count("human"),
        "apply_terms": lowered.count("apply"),
        "autonomous_terms": lowered.count("autonomous"),
        "repetition_score": _line_repetition_score([path for path in memory_files + log_files if path.suffix in {".jsonl", ".json"}]),
    }
    return signals


def build_cognitive_health_state(signals):
    invalid_count = len(signals["json_validity"]["invalid_json"])
    drift_pressure = signals["warning_terms"] + signals["critical_terms"] + signals["error_terms"]
    stability_score = max(0.0, 1.0 - min(0.75, drift_pressure / 250.0) - min(0.2, signals["repetition_score"]))
    state = "stable"
    if invalid_count or stability_score < 0.65:
        state = "warning"
    if invalid_count > 3 or stability_score < 0.4:
        state = "critical"
    return {
        "phase": "Phase 9 - Cognitive Self-Evolution",
        "layer": "Layer 1 - Cognitive Health Monitor",
        "generated_at": _now(),
        "state": "complete",
        "safety": SAFETY_CONTRACT,
        "cognitive_state": state,
        "metrics": {
            "stability_score": round(stability_score, 4),
            "drift_pressure": drift_pressure,
            "repetition_score": signals["repetition_score"],
            "memory_file_count": signals["memory_file_count"],
            "log_file_count": signals["log_file_count"],
            "json_validity": signals["json_validity"],
        },
        "analysis_only": True,
    }


def build_self_evaluation_report(signals, health):
    strengths = [
        "Safety contract is explicit and consistently represented in runtime memory.",
        "Human approval vocabulary is present across runtime artifacts.",
        "Runtime memory and logs are available for bounded self-observation.",
    ]
    weaknesses = []
    if health["cognitive_state"] != "stable":
        weaknesses.append("Cognitive state requires stabilization before any future evolution work.")
    if signals["repetition_score"] > 0.15:
        weaknesses.append("Repeated runtime lines suggest memory compaction or deduplication should be reviewed.")
    if signals["apply_terms"] > signals["approval_terms"] * 2:
        weaknesses.append("Apply-related terms appear more often than approval terms; keep gates prominent.")
    if not weaknesses:
        weaknesses.append("No critical weakness detected; continue monitoring drift and approval consistency.")
    return {
        "phase": "Phase 9 - Cognitive Self-Evolution",
        "layer": "Layer 2 - Self Evaluation Runtime",
        "generated_at": _now(),
        "state": "complete",
        "safety": SAFETY_CONTRACT,
        "evaluation_basis": ["JARVIS_CORE/runtime_memory", "JARVIS_CORE/runtime_logs"],
        "strengths": strengths,
        "weaknesses": weaknesses,
        "scores": {
            "self_observation": min(1.0, (signals["memory_file_count"] + signals["log_file_count"]) / 80.0),
            "safety_visibility": min(1.0, (signals["approval_terms"] + signals["human_terms"]) / 120.0),
            "stability": health["metrics"]["stability_score"],
        },
        "execution_allowed": False,
    }


def build_decision_quality_analysis(signals):
    approval_ratio = signals["approval_terms"] / max(1, signals["apply_terms"])
    autonomous_pressure = min(1.0, signals["autonomous_terms"] / 80.0)
    risk_score = min(1.0, (signals["warning_terms"] + signals["error_terms"] + signals["critical_terms"]) / 150.0)
    confidence_score = max(0.0, min(1.0, 0.85 - risk_score * 0.35 + min(0.1, approval_ratio / 10.0)))
    return {
        "phase": "Phase 9 - Cognitive Self-Evolution",
        "layer": "Layer 3 - Decision Quality Analyzer",
        "generated_at": _now(),
        "state": "complete",
        "safety": SAFETY_CONTRACT,
        "decision_quality": {
            "risk_score": round(risk_score, 4),
            "confidence_score": round(confidence_score, 4),
            "approval_ratio": round(approval_ratio, 4),
            "autonomous_pressure": round(autonomous_pressure, 4),
            "repetition_score": signals["repetition_score"],
        },
        "human_approval_outcome": "required_before_any_future_execution",
        "recommendation": "Keep decisions in recommendation mode until a human approves a named plan.",
    }


def build_cognitive_drift_report(signals, health, decision_quality):
    issues = []
    if health["metrics"]["json_validity"]["invalid_json"]:
        issues.append("Invalid JSON memory artifacts detected.")
    if signals["repetition_score"] > 0.15:
        issues.append("Memory repetition exceeds preferred analysis threshold.")
    if decision_quality["decision_quality"]["risk_score"] > 0.45:
        issues.append("Risk vocabulary density indicates possible drift pressure.")
    drift_state = "stable"
    if issues or health["cognitive_state"] == "warning":
        drift_state = "warning"
    if health["cognitive_state"] == "critical" or len(issues) >= 3:
        drift_state = "critical"
    return {
        "phase": "Phase 9 - Cognitive Self-Evolution",
        "layer": "Layer 4 - Cognitive Drift Detector",
        "generated_at": _now(),
        "state": "complete",
        "safety": SAFETY_CONTRACT,
        "drift_state": drift_state,
        "issues": issues or ["No critical cognitive drift detected."],
        "conflict_checks": {
            "invalid_json_count": len(health["metrics"]["json_validity"]["invalid_json"]),
            "repetition_score": signals["repetition_score"],
            "risk_score": decision_quality["decision_quality"]["risk_score"],
        },
    }


def build_self_improvement_plan(health, evaluation, drift):
    readiness = "ready_for_recommendations_only"
    if drift["drift_state"] == "warning":
        readiness = "needs_stabilization_before_evolution"
    if drift["drift_state"] == "critical":
        readiness = "blocked_until_human_review"
    return {
        "phase": "Phase 9 - Cognitive Self-Evolution",
        "layer": "Layer 5 - Self Improvement Planner",
        "generated_at": _now(),
        "state": "complete",
        "safety": SAFETY_CONTRACT,
        "plan_type": "recommendations_only",
        "improvement_readiness": readiness,
        "recommendations": [
            {
                "step": "Stabilize memory inputs",
                "action": "Review invalid or repetitive memory artifacts before adding new autonomy.",
                "execution_allowed": False,
            },
            {
                "step": "Strengthen decision receipts",
                "action": "Keep confidence, risk, and approval evidence in every future plan.",
                "execution_allowed": False,
            },
            {
                "step": "Preserve human gate",
                "action": "Require named files, test plan, rollback plan, and explicit approval phrase.",
                "execution_allowed": False,
            },
        ],
        "blocked_actions": ["autonomous_apply", "database_mutation", "deployment", "unapproved_execution"],
        "inputs": {
            "cognitive_state": health["cognitive_state"],
            "weakness_count": len(evaluation["weaknesses"]),
            "drift_state": drift["drift_state"],
        },
    }


def build_meta_cognition_state(health, evaluation, decision_quality, drift, plan):
    needs_stabilization = drift["drift_state"] != "stable" or health["cognitive_state"] != "stable"
    return {
        "phase": "Phase 9 - Cognitive Self-Evolution",
        "layer": "Layer 6 - Meta Cognition Runtime",
        "generated_at": _now(),
        "state": "complete",
        "safety": SAFETY_CONTRACT,
        "meta_cognition_state": "needs_stabilization" if needs_stabilization else "ready_for_safe_planning",
        "summary": {
            "cognitive_health": health["cognitive_state"],
            "self_evaluation_strengths": len(evaluation["strengths"]),
            "self_evaluation_weaknesses": len(evaluation["weaknesses"]),
            "decision_confidence": decision_quality["decision_quality"]["confidence_score"],
            "drift_state": drift["drift_state"],
            "improvement_readiness": plan["improvement_readiness"],
        },
        "final_guardrail": {
            "execution_allowed": False,
            "apply_allowed": False,
            "human_approval_required": True,
        },
    }


def run_phase9():
    signals = _collect_signals()
    health = build_cognitive_health_state(signals)
    _write_json(OUTPUTS["cognitive_health"], health)
    evaluation = build_self_evaluation_report(signals, health)
    _write_json(OUTPUTS["self_evaluation"], evaluation)
    decision_quality = build_decision_quality_analysis(signals)
    _write_json(OUTPUTS["decision_quality"], decision_quality)
    drift = build_cognitive_drift_report(signals, health, decision_quality)
    _write_json(OUTPUTS["cognitive_drift"], drift)
    plan = build_self_improvement_plan(health, evaluation, drift)
    _write_json(OUTPUTS["self_improvement"], plan)
    meta = build_meta_cognition_state(health, evaluation, decision_quality, drift, plan)
    _write_json(OUTPUTS["meta_cognition"], meta)
    return {
        "phase": "Phase 9 - Cognitive Self-Evolution",
        "generated_at": _now(),
        "safety": SAFETY_CONTRACT,
        "layers": {
            "layer_1_cognitive_health_monitor": "complete",
            "layer_2_self_evaluation_runtime": "complete",
            "layer_3_decision_quality_analyzer": "complete",
            "layer_4_cognitive_drift_detector": "complete",
            "layer_5_self_improvement_planner": "complete",
            "layer_6_meta_cognition_runtime": "complete",
        },
        "outputs": [str(path.relative_to(PROJECT_ROOT)).replace("\\", "/") for path in OUTPUTS.values()],
    }


if __name__ == "__main__":
    print(json.dumps(run_phase9(), ensure_ascii=False, indent=2))
