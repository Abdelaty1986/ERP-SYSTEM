import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_MEMORY = PROJECT_ROOT / "JARVIS_CORE" / "runtime_memory"

SAFETY_CONTRACT = {
    "bounded": True,
    "execution_allowed": "limited_sandbox_only",
    "apply_allowed": "staged_only",
    "autonomous_apply": False,
    "database_mutation_allowed": False,
    "deploy_allowed": False,
    "human_approval_required": True,
    "rollback_required": True,
    "checkpoint_required": True,
}

INPUT_FILES = [
    "governance_policy_engine.json",
    "approval_escalation_matrix.json",
    "simulation_decision_matrix.json",
    "simulation_readiness_report.json",
    "autonomous_planning_readiness.json",
    "approval_gateway.json",
]

OUTPUT_FILES = {
    "bridge": "execution_governance_bridge.json",
    "sandbox_policy": "sandbox_execution_policy.json",
    "queue": "controlled_execution_queue.json",
    "rollback": "controlled_rollback_checkpoint.json",
    "mutation": "controlled_mutation_engine.json",
    "approval": "execution_approval_runtime.json",
    "simulator": "autonomous_execution_simulator.json",
    "demo": "sandbox_execution_demo.json",
}

SAFE_ACTIONS = [
    "UI text changes",
    "HUD rendering changes",
    "isolated runtime test outputs",
    "safe JSON state writes",
]

BLOCKED_ACTIONS = [
    "deploy",
    "database schema changes",
    "destructive file mutation",
    "credential access",
    "external execution",
    "production mutation",
    "autonomous deployment",
    "database mutation",
    "autonomous_apply",
]


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
        "phase": "Phase 13 - Controlled Autonomous Execution",
        "layer": layer,
        "generated_at": _now(),
        "state": "complete",
        "safety": SAFETY_CONTRACT,
    }


def build_execution_governance_bridge():
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
            "error": error,
        }
    result = _base("Layer 1 - Execution Governance Bridge")
    result.update(
        {
            "inputs": inputs,
            "allowed": SAFE_ACTIONS,
            "blocked": BLOCKED_ACTIONS,
            "approval_required_for": ["every controlled execution", "every staged action", "every rollback checkpoint"],
            "rollback_checkpoint_required_for": ["every queued action", "every sandbox demonstration"],
            "bridge_state": "ready" if not missing else "blocked_missing_inputs",
        }
    )
    return result


def build_sandbox_execution_policy():
    result = _base("Layer 2 - Sandbox Execution Policy")
    result.update(
        {
            "allowed_only": SAFE_ACTIONS,
            "forbidden": BLOCKED_ACTIONS,
            "scope_boundaries": {
                "sandbox_only": True,
                "production_logic_mutation": False,
                "database_access": False,
                "network_or_external_execution": False,
                "credential_access": False,
            },
            "policy_decision": "limited_sandbox_only",
        }
    )
    return result


def build_execution_queue():
    queued_actions = [
        {
            "action_id": "ceq_hud_text_preview",
            "description": "Preview HUD text update in sandbox scope",
            "bounded": True,
            "reviewable": True,
            "reversible": True,
            "approval_state": "pending_review",
            "rollback_binding": "rb_ceq_hud_text_preview",
            "execution_scope": "sandbox_preview_only",
            "execution_state": "queued",
        },
        {
            "action_id": "ceq_runtime_json_write",
            "description": "Write isolated runtime preview JSON",
            "bounded": True,
            "reviewable": True,
            "reversible": True,
            "approval_state": "pending_review",
            "rollback_binding": "rb_ceq_runtime_json_write",
            "execution_scope": "runtime_memory_preview_only",
            "execution_state": "queued",
        },
        {
            "action_id": "ceq_safe_report_generation",
            "description": "Generate safe report artifact inside runtime memory",
            "bounded": True,
            "reviewable": True,
            "reversible": True,
            "approval_state": "pending_review",
            "rollback_binding": "rb_ceq_safe_report_generation",
            "execution_scope": "runtime_memory_preview_only",
            "execution_state": "queued",
        },
    ]
    result = _base("Layer 3 - Safe Execution Queue")
    result.update(
        {
            "queued_actions": queued_actions,
            "approval_state": "pending_review",
            "rollback_binding": "required_for_all_actions",
            "execution_scope": "limited_sandbox_only",
            "execution_state": "queued",
        }
    )
    return result


def build_rollback_checkpoint(queue):
    checkpoints = []
    for action in queue["queued_actions"]:
        checkpoints.append(
            {
                "checkpoint_id": action["rollback_binding"],
                "action_id": action["action_id"],
                "affected_files": ["JARVIS_CORE/runtime_memory/sandbox_execution_demo.json"],
                "rollback_steps": [
                    "review generated preview JSON",
                    "discard sandbox preview output if rejected",
                    "restore prior runtime_memory state from git or checkpoint copy if needed",
                ],
                "restore_strategy": "discard_preview_artifact",
                "approval_reference": "execution_approval_runtime.pending_review",
            }
        )
    result = _base("Layer 4 - Rollback Checkpoint Runtime")
    result.update({"checkpoints": checkpoints, "checkpoint_required": True, "rollback_required": True})
    return result


def build_mutation_engine():
    result = _base("Layer 5 - Controlled Mutation Engine")
    result.update(
        {
            "mutation_mode": "preview_only",
            "allowed_mutations": ["isolated sandbox mutations", "preview-only changes", "non-destructive runtime edits"],
            "blocked_mutations": ["production mutation", "autonomous deployment", "database mutation"],
            "production_mutation_allowed": False,
            "database_mutation_allowed": False,
            "deploy_allowed": False,
        }
    )
    return result


def build_execution_approval_runtime(queue, rollback):
    approvals = []
    checkpoint_ids = {item["checkpoint_id"] for item in rollback["checkpoints"]}
    for action in queue["queued_actions"]:
        approvals.append(
            {
                "action_id": action["action_id"],
                "status": "pending_review",
                "approval_token": "REQUIRES_HUMAN_APPROVAL_TOKEN",
                "checkpoint_reference": action["rollback_binding"],
                "rollback_linkage": action["rollback_binding"] in checkpoint_ids,
                "valid_states": ["pending_review", "approved", "rejected", "blocked"],
            }
        )
    result = _base("Layer 6 - Execution Approval Runtime")
    result.update({"approvals": approvals, "approval_runtime_state": "pending_review", "human_approval_required": True})
    return result


def build_execution_simulator(rollback):
    checkpoint_ids = [item["checkpoint_id"] for item in rollback["checkpoints"]]
    safe_operations = [
        ("sim_hud_text_update", "HUD text update", "sandbox_preview_only", True),
        ("sim_runtime_json_write", "runtime JSON write", "runtime_memory_preview_only", True),
        ("sim_safe_report_generation", "safe report generation", "runtime_memory_preview_only", True),
        ("sim_database_schema_change", "database schema change", "blocked", False),
        ("sim_deploy_request", "deployment request", "blocked", False),
    ]
    operations = []
    for index, (operation_id, description, scope, is_safe) in enumerate(safe_operations):
        operations.append(
            {
                "operation_id": operation_id,
                "execution_plan": {
                    "description": description,
                    "scope": scope,
                    "mode": "simulation_only" if not is_safe else "limited_sandbox_only",
                },
                "approval_required": True,
                "rollback_ready": is_safe and bool(checkpoint_ids),
                "rollback_reference": checkpoint_ids[index % len(checkpoint_ids)] if is_safe and checkpoint_ids else None,
                "execution_allowed": "limited_sandbox_only" if is_safe else False,
                "execution_blockers": [] if is_safe else ["blocked_by_policy", "requires_human_approval", "unsafe_scope"],
            }
        )
    result = _base("Layer 7 - Autonomous Execution Simulator")
    result.update({"operations": operations, "unsafe_operations_blocked": True})
    return result


def build_sandbox_demo(rollback):
    checkpoint_id = rollback["checkpoints"][0]["checkpoint_id"] if rollback["checkpoints"] else "missing_checkpoint"
    result = _base("Layer 10 - Controlled Sandbox Demonstration")
    result.update(
        {
            "demo_id": "phase13_sandbox_json_preview",
            "execution_scope": "runtime_memory_preview_only",
            "approval_state": "pending_review",
            "rollback_reference": checkpoint_id,
            "mutation_safety": {
                "sandbox_only": True,
                "production_logic_modified": False,
                "database_mutation": False,
                "deploy": False,
                "external_execution": False,
                "autonomous_apply": False,
            },
            "demo_output": {
                "type": "safe JSON preview report",
                "message": "Controlled sandbox demonstration recorded without production mutation.",
            },
        }
    )
    return result


def run_phase13():
    bridge = build_execution_governance_bridge()
    _write_json(OUTPUT_FILES["bridge"], bridge)
    policy = build_sandbox_execution_policy()
    _write_json(OUTPUT_FILES["sandbox_policy"], policy)
    queue = build_execution_queue()
    _write_json(OUTPUT_FILES["queue"], queue)
    rollback = build_rollback_checkpoint(queue)
    _write_json(OUTPUT_FILES["rollback"], rollback)
    mutation = build_mutation_engine()
    _write_json(OUTPUT_FILES["mutation"], mutation)
    approval = build_execution_approval_runtime(queue, rollback)
    _write_json(OUTPUT_FILES["approval"], approval)
    simulator = build_execution_simulator(rollback)
    _write_json(OUTPUT_FILES["simulator"], simulator)
    demo = build_sandbox_demo(rollback)
    _write_json(OUTPUT_FILES["demo"], demo)
    return {
        "phase": "Phase 13 - Controlled Autonomous Execution",
        "generated_at": _now(),
        "safety": SAFETY_CONTRACT,
        "layers": {
            "layer_1_execution_governance_bridge": "complete",
            "layer_2_sandbox_execution_policy": "complete",
            "layer_3_safe_execution_queue": "complete",
            "layer_4_rollback_checkpoint_runtime": "complete",
            "layer_5_controlled_mutation_engine": "complete",
            "layer_6_execution_approval_runtime": "complete",
            "layer_7_autonomous_execution_simulator": "complete",
            "layer_10_controlled_sandbox_demonstration": "complete",
        },
        "outputs": [f"JARVIS_CORE/runtime_memory/{name}" for name in OUTPUT_FILES.values()],
    }


if __name__ == "__main__":
    print(json.dumps(run_phase13(), ensure_ascii=False, indent=2))
