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

OUTPUT_FILES = {
    "inventory": "strategic_system_inventory.json",
    "objectives": "long_term_objectives.json",
    "roadmap": "autonomous_roadmap_plan.json",
    "impact": "strategic_impact_analysis.json",
    "decomposition": "task_decomposition_engine.json",
    "conflicts": "strategic_conflict_report.json",
    "readiness": "autonomous_planning_readiness.json",
}

GROUPS = {
    "governance_outputs": [
        "development_governance_inventory.json",
        "development_request_classifier.json",
        "governance_policy_engine.json",
        "approval_escalation_matrix.json",
        "cross_runtime_consistency_check.json",
        "autonomous_development_readiness.json",
        "governance_decision_simulator.json",
    ],
    "cognitive_outputs": [
        "cognitive_health_state.json",
        "self_evaluation_report.json",
        "decision_quality_analysis.json",
        "cognitive_drift_report.json",
        "self_improvement_plan.json",
        "meta_cognition_state.json",
    ],
    "erp_evolution_outputs": [
        "erp_module_inventory.json",
        "erp_risk_mapping.json",
        "erp_dependency_graph.json",
        "erp_safe_evolution_plan.json",
        "erp_human_approval_gateway.json",
    ],
    "agent_society_outputs": [
        "agent_routing_memory.json",
        "agent_skill_memory.json",
        "agent_society_aggregate_state.json",
        "agent_society_consensus.json",
        "agent_society_delegation.json",
        "agent_society_event_summary.json",
        "agent_society_orchestrator.json",
        "agent_society_registry.json",
        "agent_society_routing.json",
    ],
    "provider_intelligence_outputs": [
        "provider_model_validation.json",
        "provider_scoring_memory.json",
        "provider_strategy_memory.json",
        "provider_trust_memory.json",
        "model_discovery_snapshot.json",
        "model_trust_memory.json",
        "adaptive_routing_recommendations.json",
    ],
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _path(file_name):
    return RUNTIME_MEMORY / file_name


def _load_json(file_name):
    path = _path(file_name)
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)


def _write_json(file_name, payload):
    RUNTIME_MEMORY.mkdir(parents=True, exist_ok=True)
    _path(file_name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _base_payload(layer):
    return {
        "phase": "Phase 11 - Autonomous Strategic Planning",
        "layer": layer,
        "generated_at": _now(),
        "state": "complete",
        "safety": SAFETY_CONTRACT,
    }


def _summarize_file(file_name):
    payload, error = _load_json(file_name)
    exists = payload is not None
    return {
        "file": f"JARVIS_CORE/runtime_memory/{file_name}",
        "exists": exists,
        "state": payload.get("state", "unknown") if isinstance(payload, dict) else "missing",
        "safety_matches": payload.get("safety") == SAFETY_CONTRACT if isinstance(payload, dict) and "safety" in payload else None,
        "top_level_keys": sorted(payload.keys())[:12] if isinstance(payload, dict) else [],
        "error": error,
    }


def build_strategic_system_inventory():
    groups = {}
    missing = []
    warnings = []
    for group, files in GROUPS.items():
        entries = {}
        for file_name in files:
            summary = _summarize_file(file_name)
            entries[file_name] = summary
            if not summary["exists"]:
                missing.append(file_name)
            if summary["safety_matches"] is False:
                warnings.append(f"{file_name} safety contract mismatch")
        groups[group] = entries
    all_files = list(RUNTIME_MEMORY.glob("*.json")) if RUNTIME_MEMORY.exists() else []
    payload = _base_payload("Layer 1 - Strategic System Inventory")
    payload.update(
        {
            "groups": groups,
            "runtime_memory_file_count": len(all_files),
            "summary": {
                "expected_inputs": sum(len(files) for files in GROUPS.values()),
                "missing_inputs": missing,
                "warnings": warnings,
                "strategic_picture": "governed_planning_stack_available" if not missing else "partial_context_available",
            },
        }
    )
    return payload


def build_long_term_objectives(inventory):
    missing = inventory["summary"]["missing_inputs"]
    base_safety = "human_approval_required"
    payload = _base_payload("Layer 2 - Long-Term Objective Engine")
    payload.update(
        {
            "short_term_goals": [
                {
                    "goal": "Keep ERP evolution and cognitive governance outputs synchronized",
                    "priority": "high",
                    "complexity": "medium",
                    "estimated_impact": "improves planning quality and reduces drift",
                    "safety_level": base_safety,
                },
                {
                    "goal": "Maintain Mobile Control Center visibility for runtime safety states",
                    "priority": "medium",
                    "complexity": "low",
                    "estimated_impact": "improves human review speed",
                    "safety_level": base_safety,
                },
            ],
            "mid_term_goals": [
                {
                    "goal": "Create repeatable strategic planning cycles from governance and cognition memory",
                    "priority": "high",
                    "complexity": "medium",
                    "estimated_impact": "turns phase outputs into stable roadmaps",
                    "safety_level": base_safety,
                },
                {
                    "goal": "Improve provider and agent coordination scoring for future recommendations",
                    "priority": "medium",
                    "complexity": "medium",
                    "estimated_impact": "better agent selection without autonomous execution",
                    "safety_level": base_safety,
                },
            ],
            "long_term_goals": [
                {
                    "goal": "Build a governed ERP modernization roadmap with explicit approval gates",
                    "priority": "high",
                    "complexity": "high",
                    "estimated_impact": "safe long-term ERP evolution",
                    "safety_level": base_safety,
                },
                {
                    "goal": "Establish strategic impact forecasting before any implementation proposal",
                    "priority": "high",
                    "complexity": "high",
                    "estimated_impact": "reduces cross-system regression risk",
                    "safety_level": base_safety,
                },
            ],
            "inventory_gaps": missing,
        }
    )
    return payload


def build_roadmap_plan(inventory, objectives):
    has_gaps = bool(inventory["summary"]["missing_inputs"])
    payload = _base_payload("Layer 3 - Autonomous Roadmap Planner")
    payload.update(
        {
            "current_stage": "governed_analysis_stack",
            "next_required_stage": "stabilize_and_refresh_memory_inputs" if has_gaps else "strategic_planning_review",
            "optional_future_stages": [
                "quarterly ERP modernization roadmap",
                "provider coordination review cycle",
                "agent society responsibility matrix",
                "human-approved implementation proposal workflow",
            ],
            "blocked_stages": [
                "autonomous_apply",
                "database_schema_mutation",
                "deployment_execution",
                "unapproved production file changes",
            ],
            "dependencies": {
                "short_term": [item["goal"] for item in objectives["short_term_goals"]],
                "mid_term": [item["goal"] for item in objectives["mid_term_goals"]],
                "long_term": [item["goal"] for item in objectives["long_term_goals"]],
            },
            "governance_requirements": [
                "human approval before execution",
                "risk classification before planning",
                "rollback plan before approved implementation",
                "database and deploy changes blocked by default",
            ],
        }
    )
    return payload


def build_impact_analysis():
    domains = [
        "runtime_stability",
        "governance",
        "erp_safety",
        "cognitive_integrity",
        "provider_coordination",
        "agent_society",
    ]
    scenarios = {
        "ui_hud_update": ["low", "medium", "low", "low", "low", "low"],
        "erp_route_change": ["medium", "high", "high", "medium", "low", "medium"],
        "runtime_governance_change": ["high", "high", "medium", "high", "medium", "high"],
        "provider_strategy_change": ["medium", "medium", "low", "medium", "high", "medium"],
        "database_schema_change": ["critical", "critical", "critical", "high", "medium", "medium"],
    }
    matrix = {
        scenario: dict(zip(domains, levels))
        for scenario, levels in scenarios.items()
    }
    payload = _base_payload("Layer 4 - Strategic Impact Analyzer")
    payload.update(
        {
            "impact_matrix": matrix,
            "impact_domains": domains,
            "global_rule": "Any high or critical impact requires human approval and remains planning-only until approved.",
        }
    )
    return payload


def build_task_decomposition(objectives):
    execution_phases = []
    for index, goal in enumerate(objectives["long_term_goals"], start=1):
        execution_phases.append(
            {
                "phase": f"strategic_phase_{index}",
                "goal": goal["goal"],
                "subtasks": [
                    "refresh inventory",
                    "classify risk",
                    "build proposal",
                    "request human review",
                    "wait for explicit approval",
                ],
                "dependency_chain": [
                    "strategic_system_inventory",
                    "governance_policy_engine",
                    "impact_analysis",
                    "approval_escalation",
                ],
                "risk_estimate": goal["complexity"],
                "safe_sequence": "analysis -> planning -> review -> approval gate",
                "execution_allowed": False,
            }
        )
    payload = _base_payload("Layer 5 - Task Decomposition Engine")
    payload.update(
        {
            "execution_phases": execution_phases,
            "safe_sequencing_rules": [
                "Never skip risk classification.",
                "Never move from plan to apply without human approval.",
                "Database and deploy work are blocked until explicitly approved.",
            ],
        }
    )
    return payload


def build_conflict_report(inventory, roadmap):
    conflicts = []
    missing = inventory["summary"]["missing_inputs"]
    if missing:
        conflicts.append({"type": "inventory_gap", "items": missing})
    blocked = roadmap["blocked_stages"]
    if "autonomous_apply" not in blocked:
        conflicts.append({"type": "governance_gap", "items": ["autonomous_apply not blocked"]})
    meta, _ = _load_json("meta_cognition_state.json")
    readiness, _ = _load_json("autonomous_development_readiness.json")
    if isinstance(meta, dict) and meta.get("safety") != SAFETY_CONTRACT:
        conflicts.append({"type": "cognitive_contract", "items": ["meta cognition safety mismatch"]})
    if isinstance(readiness, dict) and readiness.get("readiness_state") == "blocked":
        conflicts.append({"type": "governance_readiness", "items": ["development readiness blocked"]})
    state = "stable"
    if conflicts:
        state = "warning"
    if any(conflict["type"] in {"governance_gap", "cognitive_contract"} for conflict in conflicts):
        state = "blocked"
    payload = _base_payload("Layer 6 - Strategic Conflict Detector")
    payload.update(
        {
            "conflict_state": state,
            "conflicts": conflicts,
            "checked_boundaries": [
                "goals",
                "governance",
                "runtime limits",
                "cognitive state",
                "approval policies",
            ],
        }
    )
    return payload


def build_planning_readiness(conflict_report, impact_analysis):
    conflict_state = conflict_report["conflict_state"]
    critical_impacts = sum(
        1
        for scenario in impact_analysis["impact_matrix"].values()
        for level in scenario.values()
        if level == "critical"
    )
    readiness_score = 0.86
    if conflict_state == "warning":
        readiness_score -= 0.22
    if conflict_state == "blocked":
        readiness_score -= 0.5
    readiness_score -= min(0.12, critical_impacts * 0.02)
    readiness_score = max(0.0, round(readiness_score, 4))
    if conflict_state == "blocked" or readiness_score < 0.4:
        readiness = "blocked"
    elif conflict_state == "warning" or readiness_score < 0.7:
        readiness = "needs_stabilization"
    else:
        readiness = "planning_ready"
    payload = _base_payload("Layer 7 - Autonomous Planning Readiness")
    payload.update(
        {
            "planning_readiness": readiness,
            "readiness_score": readiness_score,
            "blockers": conflict_report["conflicts"],
            "recommended_actions": [
                "Keep strategic planning in recommendation mode.",
                "Refresh governance and cognitive outputs before future planning cycles.",
                "Require human approval before any implementation proposal moves to execution.",
            ],
        }
    )
    return payload


def run_phase11():
    inventory = build_strategic_system_inventory()
    _write_json(OUTPUT_FILES["inventory"], inventory)
    objectives = build_long_term_objectives(inventory)
    _write_json(OUTPUT_FILES["objectives"], objectives)
    roadmap = build_roadmap_plan(inventory, objectives)
    _write_json(OUTPUT_FILES["roadmap"], roadmap)
    impact = build_impact_analysis()
    _write_json(OUTPUT_FILES["impact"], impact)
    decomposition = build_task_decomposition(objectives)
    _write_json(OUTPUT_FILES["decomposition"], decomposition)
    conflicts = build_conflict_report(inventory, roadmap)
    _write_json(OUTPUT_FILES["conflicts"], conflicts)
    readiness = build_planning_readiness(conflicts, impact)
    _write_json(OUTPUT_FILES["readiness"], readiness)
    return {
        "phase": "Phase 11 - Autonomous Strategic Planning",
        "generated_at": _now(),
        "safety": SAFETY_CONTRACT,
        "layers": {
            "layer_1_strategic_system_inventory": "complete",
            "layer_2_long_term_objective_engine": "complete",
            "layer_3_autonomous_roadmap_planner": "complete",
            "layer_4_strategic_impact_analyzer": "complete",
            "layer_5_task_decomposition_engine": "complete",
            "layer_6_strategic_conflict_detector": "complete",
            "layer_7_autonomous_planning_readiness": "complete",
        },
        "outputs": [
            f"JARVIS_CORE/runtime_memory/{file_name}"
            for file_name in OUTPUT_FILES.values()
        ],
    }


if __name__ == "__main__":
    print(json.dumps(run_phase11(), ensure_ascii=False, indent=2))
