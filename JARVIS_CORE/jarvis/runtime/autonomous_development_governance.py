import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_MEMORY = PROJECT_ROOT / "JARVIS_CORE" / "runtime_memory"

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

INPUT_FILES = {
    "erp_module_inventory": "erp_module_inventory.json",
    "erp_risk_mapping": "erp_risk_mapping.json",
    "erp_safe_evolution_plan": "erp_safe_evolution_plan.json",
    "erp_human_approval_gateway": "erp_human_approval_gateway.json",
    "cognitive_health_state": "cognitive_health_state.json",
    "self_evaluation_report": "self_evaluation_report.json",
    "decision_quality_analysis": "decision_quality_analysis.json",
    "cognitive_drift_report": "cognitive_drift_report.json",
    "meta_cognition_state": "meta_cognition_state.json",
    "agent_routing_memory": "agent_routing_memory.json",
    "agent_skill_memory": "agent_skill_memory.json",
    "approval_gateway": "approval_gateway.json",
}

OUTPUT_FILES = {
    "governance_inventory": "development_governance_inventory.json",
    "request_classifier": "development_request_classifier.json",
    "policy_engine": "governance_policy_engine.json",
    "approval_escalation": "approval_escalation_matrix.json",
    "consistency_check": "cross_runtime_consistency_check.json",
    "readiness": "autonomous_development_readiness.json",
    "decision_simulator": "governance_decision_simulator.json",
}

CHANGE_TYPES = [
    "ui_change",
    "backend_change",
    "database_change",
    "runtime_change",
    "agent_change",
    "deployment_change",
    "unknown",
]

RISK_BY_TYPE = {
    "ui_change": "low",
    "backend_change": "high",
    "database_change": "critical",
    "runtime_change": "high",
    "agent_change": "medium",
    "deployment_change": "critical",
    "unknown": "medium",
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _runtime_path(file_name):
    return RUNTIME_MEMORY / file_name


def _load_json(file_name):
    path = _runtime_path(file_name)
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)


def _write_json(file_name, payload):
    RUNTIME_MEMORY.mkdir(parents=True, exist_ok=True)
    _runtime_path(file_name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _base_payload(layer):
    return {
        "phase": "Phase 10 - Autonomous Development Governance",
        "layer": layer,
        "generated_at": _now(),
        "state": "complete",
        "safety": SAFETY_CONTRACT,
    }


def build_governance_inventory():
    systems = {}
    missing = []
    safety_mismatches = []
    for key, file_name in INPUT_FILES.items():
        payload, error = _load_json(file_name)
        exists = payload is not None
        safety = payload.get("safety") if isinstance(payload, dict) else None
        if not exists:
            missing.append(file_name)
        if safety is not None and safety != SAFETY_CONTRACT:
            safety_mismatches.append(file_name)
        systems[key] = {
            "file": f"JARVIS_CORE/runtime_memory/{file_name}",
            "exists": exists,
            "state": payload.get("state", "unknown") if isinstance(payload, dict) else "missing",
            "safety_present": safety is not None,
            "safety_matches_phase10": safety == SAFETY_CONTRACT if safety is not None else None,
            "error": error,
        }
    payload = _base_payload("Layer 1 - Development Governance Inventory")
    payload.update(
        {
            "systems": systems,
            "summary": {
                "inputs_expected": len(INPUT_FILES),
                "inputs_available": len(INPUT_FILES) - len(missing),
                "missing": missing,
                "safety_mismatches": safety_mismatches,
            },
            "analysis_only": True,
        }
    )
    return payload


def classify_request(text):
    lowered = text.lower()
    if any(word in lowered for word in ["deploy", "release", "production", "hosting"]):
        kind = "deployment_change"
    elif any(word in lowered for word in ["schema", "migration", "database", "db", "table", "sql"]):
        kind = "database_change"
    elif any(word in lowered for word in ["agent", "routing", "skill", "provider"]):
        kind = "agent_change"
    elif any(word in lowered for word in ["runtime", "jarvis", "memory", "approval", "governance"]):
        kind = "runtime_change"
    elif any(word in lowered for word in ["route", "api", "backend", "view", "controller", "module"]):
        kind = "backend_change"
    elif any(word in lowered for word in ["ui", "hud", "template", "css", "static", "mobile control"]):
        kind = "ui_change"
    else:
        kind = "unknown"
    return {"classification": kind, "risk": RISK_BY_TYPE[kind]}


def _policy_for_risk(risk):
    if risk == "low":
        return {
            "decision": "planning_only",
            "allowed_actions": ["analysis", "planning", "proposal"],
            "blocked_actions": ["apply", "deploy", "database_mutation", "autonomous_apply"],
            "approval_required": True,
        }
    if risk == "medium":
        return {
            "decision": "plan_plus_human_review",
            "allowed_actions": ["analysis", "planning", "human_review_request"],
            "blocked_actions": ["apply", "deploy", "database_mutation", "autonomous_apply"],
            "approval_required": True,
        }
    if risk == "high":
        return {
            "decision": "human_approval_required",
            "allowed_actions": ["analysis", "planning", "risk_report"],
            "blocked_actions": ["apply", "deploy", "database_mutation", "autonomous_apply"],
            "approval_required": True,
        }
    return {
        "decision": "blocked_unless_explicitly_approved",
        "allowed_actions": ["analysis", "planning", "escalation_report"],
        "blocked_actions": ["apply", "deploy", "database_mutation", "autonomous_apply"],
        "approval_required": True,
    }


def build_request_classifier():
    examples = {
        "UI HUD update": classify_request("UI HUD update"),
        "ERP route change": classify_request("ERP route change"),
        "database schema change": classify_request("database schema change"),
        "agent routing update": classify_request("agent routing update"),
        "deployment request": classify_request("deployment request"),
        "unrecognized development work": classify_request("unrecognized development work"),
    }
    payload = _base_payload("Layer 2 - Development Request Classifier")
    payload.update(
        {
            "supported_classifications": CHANGE_TYPES,
            "risk_levels": ["low", "medium", "high", "critical"],
            "classifier_rules": {
                "ui_change": ["ui", "hud", "template", "css", "static"],
                "backend_change": ["route", "api", "backend", "view", "controller", "module"],
                "database_change": ["schema", "migration", "database", "db", "table", "sql"],
                "runtime_change": ["runtime", "jarvis", "memory", "approval", "governance"],
                "agent_change": ["agent", "routing", "skill", "provider"],
                "deployment_change": ["deploy", "release", "production", "hosting"],
                "unknown": ["fallback when no rule matches"],
            },
            "default_examples": examples,
        }
    )
    return payload


def build_policy_engine():
    payload = _base_payload("Layer 3 - Governance Policy Engine")
    payload.update(
        {
            "policies": {risk: _policy_for_risk(risk) for risk in ["low", "medium", "high", "critical"]},
            "global_blocks": {
                "database_mutation_allowed": False,
                "deploy_allowed": False,
                "autonomous_apply": False,
                "apply_allowed": False,
                "execution_allowed": False,
            },
            "human_approval_required": True,
        }
    )
    return payload


def build_approval_escalation_matrix(policy_engine):
    matrix = {}
    for change_type in CHANGE_TYPES:
        risk = RISK_BY_TYPE[change_type]
        policy = policy_engine["policies"][risk]
        matrix[change_type] = {
            "risk": risk,
            "who_approves": "human",
            "what_is_allowed": policy["allowed_actions"],
            "what_is_blocked": policy["blocked_actions"],
            "approval_required": True,
        }
    payload = _base_payload("Layer 4 - Approval Escalation Matrix")
    payload.update({"matrix": matrix})
    return payload


def build_consistency_check(inventory):
    checks = []
    systems = inventory["systems"]
    for key in [
        "approval_gateway",
        "erp_human_approval_gateway",
        "meta_cognition_state",
        "decision_quality_analysis",
    ]:
        checks.append(
            {
                "system": key,
                "exists": systems[key]["exists"],
                "state": systems[key]["state"],
                "safety_matches": systems[key]["safety_matches_phase10"],
            }
        )
    conflicts = []
    for check in checks:
        if not check["exists"]:
            conflicts.append(f"{check['system']} is missing")
        if check["safety_matches"] is False:
            conflicts.append(f"{check['system']} safety contract mismatch")
    erp_gateway, _ = _load_json(INPUT_FILES["erp_human_approval_gateway"])
    meta_state, _ = _load_json(INPUT_FILES["meta_cognition_state"])
    decision_quality, _ = _load_json(INPUT_FILES["decision_quality_analysis"])
    if isinstance(erp_gateway, dict) and erp_gateway.get("safety") != SAFETY_CONTRACT:
        conflicts.append("ERP approval gateway is not aligned with Phase 10 safety contract")
    if isinstance(meta_state, dict):
        final_guardrail = meta_state.get("final_guardrail", {})
        if final_guardrail.get("execution_allowed") is not False:
            conflicts.append("Meta cognition final guardrail allows execution")
    if isinstance(decision_quality, dict):
        if decision_quality.get("human_approval_outcome") != "required_before_any_future_execution":
            conflicts.append("Decision quality does not require human approval before execution")
    payload = _base_payload("Layer 5 - Cross Runtime Consistency Check")
    payload.update(
        {
            "consistency_state": "consistent" if not conflicts else "warning",
            "checks": checks,
            "conflicts": conflicts,
            "blocked_if_conflicts": bool(conflicts),
        }
    )
    return payload


def build_readiness(consistency_check):
    if consistency_check["conflicts"]:
        readiness = "needs_stabilization"
    else:
        meta_state, _ = _load_json(INPUT_FILES["meta_cognition_state"])
        drift_report, _ = _load_json(INPUT_FILES["cognitive_drift_report"])
        meta_value = meta_state.get("meta_cognition_state") if isinstance(meta_state, dict) else "unknown"
        drift_value = drift_report.get("drift_state") if isinstance(drift_report, dict) else "unknown"
        if drift_value == "critical":
            readiness = "blocked"
        elif meta_value == "needs_stabilization" or drift_value == "warning":
            readiness = "needs_stabilization"
        else:
            readiness = "ready_for_planning"
    payload = _base_payload("Layer 6 - Autonomous Development Readiness")
    payload.update(
        {
            "readiness_state": readiness,
            "execution_allowed": False,
            "apply_allowed": False,
            "notes": [
                "Readiness only controls planning and governance recommendations.",
                "No implementation, database mutation, deploy, or autonomous apply is allowed.",
            ],
        }
    )
    return payload


def build_decision_simulator(policy_engine):
    simulated_requests = [
        "UI HUD update",
        "ERP route change",
        "database schema change",
        "agent routing update",
        "deployment request",
    ]
    simulations = []
    for request in simulated_requests:
        classification = classify_request(request)
        policy = policy_engine["policies"][classification["risk"]]
        simulations.append(
            {
                "request": request,
                "classification": classification["classification"],
                "risk": classification["risk"],
                "decision": policy["decision"],
                "allowed_actions": policy["allowed_actions"],
                "blocked_actions": policy["blocked_actions"],
                "approval_required": policy["approval_required"],
            }
        )
    payload = _base_payload("Layer 7 - Governance Decision Simulator")
    payload.update({"simulations": simulations, "simulation_mode": "analysis_only"})
    return payload


def run_phase10():
    inventory = build_governance_inventory()
    _write_json(OUTPUT_FILES["governance_inventory"], inventory)
    classifier = build_request_classifier()
    _write_json(OUTPUT_FILES["request_classifier"], classifier)
    policy_engine = build_policy_engine()
    _write_json(OUTPUT_FILES["policy_engine"], policy_engine)
    escalation = build_approval_escalation_matrix(policy_engine)
    _write_json(OUTPUT_FILES["approval_escalation"], escalation)
    consistency = build_consistency_check(inventory)
    _write_json(OUTPUT_FILES["consistency_check"], consistency)
    readiness = build_readiness(consistency)
    _write_json(OUTPUT_FILES["readiness"], readiness)
    simulator = build_decision_simulator(policy_engine)
    _write_json(OUTPUT_FILES["decision_simulator"], simulator)
    return {
        "phase": "Phase 10 - Autonomous Development Governance",
        "generated_at": _now(),
        "safety": SAFETY_CONTRACT,
        "layers": {
            "layer_1_development_governance_inventory": "complete",
            "layer_2_development_request_classifier": "complete",
            "layer_3_governance_policy_engine": "complete",
            "layer_4_approval_escalation_matrix": "complete",
            "layer_5_cross_runtime_consistency_check": "complete",
            "layer_6_autonomous_development_readiness": "complete",
            "layer_7_governance_decision_simulator": "complete",
        },
        "outputs": [
            f"JARVIS_CORE/runtime_memory/{file_name}"
            for file_name in OUTPUT_FILES.values()
        ],
    }


if __name__ == "__main__":
    print(json.dumps(run_phase10(), ensure_ascii=False, indent=2))
