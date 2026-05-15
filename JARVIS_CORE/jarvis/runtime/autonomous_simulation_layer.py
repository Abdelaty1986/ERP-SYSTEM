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

INPUT_FILES = [
    "autonomous_roadmap_plan.json",
    "strategic_impact_analysis.json",
    "task_decomposition_engine.json",
    "autonomous_planning_readiness.json",
    "governance_policy_engine.json",
    "approval_escalation_matrix.json",
    "autonomous_development_readiness.json",
    "erp_dependency_graph.json",
    "erp_risk_mapping.json",
    "cognitive_health_state.json",
    "meta_cognition_state.json",
]

OUTPUT_FILES = {
    "context": "simulation_context_inventory.json",
    "scenarios": "change_scenario_generator.json",
    "impact": "impact_simulation_engine.json",
    "failure": "failure_forecast_engine.json",
    "rollback": "rollback_simulation_plan.json",
    "decision": "simulation_decision_matrix.json",
    "readiness": "simulation_readiness_report.json",
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _path(file_name):
    return RUNTIME_MEMORY / file_name


def _load_json(file_name):
    try:
        with _path(file_name).open("r", encoding="utf-8") as handle:
            return json.load(handle), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)


def _write_json(file_name, payload):
    RUNTIME_MEMORY.mkdir(parents=True, exist_ok=True)
    _path(file_name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _base(layer):
    return {
        "phase": "Phase 12 - Autonomous Simulation Layer",
        "layer": layer,
        "generated_at": _now(),
        "state": "complete",
        "safety": SAFETY_CONTRACT,
    }


def build_context_inventory():
    inputs = {}
    missing = []
    for file_name in INPUT_FILES:
        payload, error = _load_json(file_name)
        exists = payload is not None
        if not exists:
            missing.append(file_name)
        inputs[file_name] = {
            "file": f"JARVIS_CORE/runtime_memory/{file_name}",
            "exists": exists,
            "state": payload.get("state", "unknown") if isinstance(payload, dict) else "missing",
            "safety_matches": payload.get("safety") == SAFETY_CONTRACT if isinstance(payload, dict) and "safety" in payload else None,
            "error": error,
        }
    result = _base("Layer 1 - Simulation Context Inventory")
    result.update(
        {
            "inputs": inputs,
            "summary": {
                "expected_inputs": len(INPUT_FILES),
                "available_inputs": len(INPUT_FILES) - len(missing),
                "missing_inputs": missing,
                "simulation_context": "complete" if not missing else "partial",
            },
            "production_mutation": False,
        }
    )
    return result


def build_scenarios():
    scenarios = [
        ("sim_ui_hud_update", "ui_change", "UI HUD update", "low", ["templates", "runtime_memory"]),
        ("sim_erp_workflow_improvement", "backend_change", "ERP workflow improvement", "high", ["erp", "routes", "templates"]),
        ("sim_runtime_module_update", "runtime_change", "runtime module update", "high", ["runtime", "governance"]),
        ("sim_agent_routing_adjustment", "agent_change", "agent routing adjustment", "medium", ["agent_society", "provider_coordination"]),
        ("sim_database_schema_proposal", "database_change", "database schema proposal", "critical", ["database", "erp", "rollback"]),
        ("sim_deployment_proposal", "deployment_change", "deployment proposal", "critical", ["deploy", "runtime_safety"]),
    ]
    result = _base("Layer 2 - Change Scenario Generator")
    result.update(
        {
            "scenarios": [
                {
                    "scenario_id": scenario_id,
                    "change_type": change_type,
                    "description": description,
                    "estimated_risk": risk,
                    "affected_layers": layers,
                    "requires_human_approval": True,
                }
                for scenario_id, change_type, description, risk, layers in scenarios
            ],
            "generation_mode": "safe_hypothetical",
        }
    )
    return result


def _impact_for_risk(risk):
    if risk == "low":
        return {"runtime_stability": "low", "ERP_safety": "low", "governance_consistency": "low", "cognitive_integrity": "low", "agent_society": "low", "provider_coordination": "low"}
    if risk == "medium":
        return {"runtime_stability": "medium", "ERP_safety": "low", "governance_consistency": "medium", "cognitive_integrity": "medium", "agent_society": "high", "provider_coordination": "high"}
    if risk == "high":
        return {"runtime_stability": "high", "ERP_safety": "high", "governance_consistency": "high", "cognitive_integrity": "medium", "agent_society": "medium", "provider_coordination": "medium"}
    return {"runtime_stability": "critical", "ERP_safety": "critical", "governance_consistency": "critical", "cognitive_integrity": "high", "agent_society": "medium", "provider_coordination": "medium"}


def build_impact_engine(scenarios):
    result = _base("Layer 3 - Impact Simulation Engine")
    result.update(
        {
            "simulations": [
                {
                    "scenario_id": scenario["scenario_id"],
                    "change_type": scenario["change_type"],
                    "impact": _impact_for_risk(scenario["estimated_risk"]),
                    "production_files_modified": False,
                }
                for scenario in scenarios["scenarios"]
            ],
            "simulation_only": True,
        }
    )
    return result


def build_failure_forecast(scenarios):
    forecasts = []
    for scenario in scenarios["scenarios"]:
        risk = scenario["estimated_risk"]
        flags = {
            "broken_dependency": risk in {"high", "critical"},
            "unsafe_mutation": risk in {"high", "critical"},
            "approval_bypass_risk": True,
            "database_mutation_risk": scenario["change_type"] == "database_change",
            "UI_regression": scenario["change_type"] in {"ui_change", "backend_change"},
            "runtime_drift": scenario["change_type"] in {"runtime_change", "agent_change", "deployment_change"},
        }
        forecasts.append({"scenario_id": scenario["scenario_id"], "estimated_risk": risk, "failure_modes": flags})
    result = _base("Layer 4 - Failure Forecast Engine")
    result.update({"forecasts": forecasts})
    return result


def build_rollback_plan(scenarios):
    complexity = {"low": "low", "medium": "medium", "high": "high", "critical": "critical"}
    result = _base("Layer 5 - Rollback Simulation Planner")
    result.update(
        {
            "rollback_plans": [
                {
                    "scenario_id": scenario["scenario_id"],
                    "rollback_required": True,
                    "rollback_complexity": complexity[scenario["estimated_risk"]],
                    "rollback_steps": [
                        "capture pre-change checkpoint",
                        "validate proposed diff in sandbox",
                        "prepare manual rollback instructions",
                        "require human approval before any real execution",
                    ],
                    "checkpoint_needed": True,
                    "approval_needed": True,
                }
                for scenario in scenarios["scenarios"]
            ]
        }
    )
    return result


def build_decision_matrix(scenarios):
    matrix = []
    for scenario in scenarios["scenarios"]:
        risk = scenario["estimated_risk"]
        matrix.append(
            {
                "scenario_id": scenario["scenario_id"],
                "change_type": scenario["change_type"],
                "risk": risk,
                "safe_to_plan": True,
                "safe_to_stage": risk in {"low", "medium"},
                "safe_to_execute": False,
                "blocked": risk == "critical",
                "approval_required": True,
                "blocked_actions": ["apply", "deploy", "database_mutation", "autonomous_apply"],
            }
        )
    result = _base("Layer 6 - Simulation Decision Matrix")
    result.update({"decisions": matrix, "all_safe_to_execute_false": all(not item["safe_to_execute"] for item in matrix)})
    return result


def build_readiness(decision_matrix, context):
    critical_blocks = sum(1 for item in decision_matrix["decisions"] if item["blocked"])
    missing = context["summary"]["missing_inputs"]
    if missing:
        readiness = "blocked"
    elif critical_blocks:
        readiness = "needs_more_validation"
    else:
        readiness = "simulation_ready"
    result = _base("Layer 7 - Simulation Readiness Report")
    result.update(
        {
            "readiness_state": readiness,
            "controlled_execution_readiness": "not_allowed_without_human_approval",
            "critical_blocked_scenarios": critical_blocks,
            "safe_to_execute_any": False,
            "recommended_actions": [
                "Keep all scenarios in simulation mode.",
                "Require human approval before controlled execution planning.",
                "Re-run probes after any new governance or ERP memory output.",
            ],
        }
    )
    return result


def run_phase12():
    context = build_context_inventory()
    _write_json(OUTPUT_FILES["context"], context)
    scenarios = build_scenarios()
    _write_json(OUTPUT_FILES["scenarios"], scenarios)
    impact = build_impact_engine(scenarios)
    _write_json(OUTPUT_FILES["impact"], impact)
    failure = build_failure_forecast(scenarios)
    _write_json(OUTPUT_FILES["failure"], failure)
    rollback = build_rollback_plan(scenarios)
    _write_json(OUTPUT_FILES["rollback"], rollback)
    decision = build_decision_matrix(scenarios)
    _write_json(OUTPUT_FILES["decision"], decision)
    readiness = build_readiness(decision, context)
    _write_json(OUTPUT_FILES["readiness"], readiness)
    return {
        "phase": "Phase 12 - Autonomous Simulation Layer",
        "generated_at": _now(),
        "safety": SAFETY_CONTRACT,
        "layers": {
            "layer_1_simulation_context_inventory": "complete",
            "layer_2_change_scenario_generator": "complete",
            "layer_3_impact_simulation_engine": "complete",
            "layer_4_failure_forecast_engine": "complete",
            "layer_5_rollback_simulation_planner": "complete",
            "layer_6_simulation_decision_matrix": "complete",
            "layer_7_simulation_readiness_report": "complete",
        },
        "outputs": [f"JARVIS_CORE/runtime_memory/{name}" for name in OUTPUT_FILES.values()],
    }


if __name__ == "__main__":
    print(json.dumps(run_phase12(), ensure_ascii=False, indent=2))
