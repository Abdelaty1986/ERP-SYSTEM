import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_MEMORY = PROJECT_ROOT / "JARVIS_CORE" / "runtime_memory"
HUD_FILE = PROJECT_ROOT / "templates" / "jarvis" / "mobile_control_center.html"

EXPECTED_FILES = {
    "layer_1_bridge": "execution_governance_bridge.json",
    "layer_2_policy": "sandbox_execution_policy.json",
    "layer_3_queue": "controlled_execution_queue.json",
    "layer_4_rollback": "controlled_rollback_checkpoint.json",
    "layer_5_mutation": "controlled_mutation_engine.json",
    "layer_6_approval": "execution_approval_runtime.json",
    "layer_7_simulator": "autonomous_execution_simulator.json",
    "layer_10_demo": "sandbox_execution_demo.json",
}

EXPECTED_SAFETY = {
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

HUD_MARKERS = [
    "phase13-controlled-execution-panel",
    "Execution Governance",
    "Sandbox Policy",
    "Execution Queue",
    "Rollback Readiness",
    "Approval Runtime",
    "Execution Simulator",
    "Blocked Actions",
    "execution=Limited Sandbox Only",
    "database_mutation=No",
    "autonomous_apply=Off",
    "human_approval=Yes",
]


def _load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _all_execution_limited():
    simulator = _load_json(RUNTIME_MEMORY / "autonomous_execution_simulator.json")
    allowed = [item for item in simulator.get("operations", []) if item.get("execution_allowed")]
    return all(item.get("execution_allowed") == "limited_sandbox_only" for item in allowed)


def _all_execution_has_rollback():
    simulator = _load_json(RUNTIME_MEMORY / "autonomous_execution_simulator.json")
    rollback = _load_json(RUNTIME_MEMORY / "controlled_rollback_checkpoint.json")
    checkpoint_ids = {item.get("checkpoint_id") for item in rollback.get("checkpoints", [])}
    for item in simulator.get("operations", []):
        if item.get("execution_allowed") == "limited_sandbox_only":
            if not item.get("rollback_ready") or item.get("rollback_reference") not in checkpoint_ids:
                return False
    return True


def probe_phase13():
    layers = {}
    all_ok = True
    for layer_name, file_name in EXPECTED_FILES.items():
        path = RUNTIME_MEMORY / file_name
        result = {
            "file": f"JARVIS_CORE/runtime_memory/{file_name}",
            "exists": path.exists(),
            "valid_json": False,
            "state": "missing",
            "safety_ok": False,
            "ok": False,
        }
        if path.exists():
            try:
                payload = _load_json(path)
                result["valid_json"] = True
                result["state"] = payload.get("state", "unknown")
                result["safety_ok"] = payload.get("safety") == EXPECTED_SAFETY
            except (OSError, json.JSONDecodeError) as exc:
                result["error"] = str(exc)
        result["ok"] = result["exists"] and result["valid_json"] and result["state"] == "complete" and result["safety_ok"]
        all_ok = all_ok and result["ok"]
        layers[layer_name] = result

    rollback_ok = _all_execution_has_rollback()
    execution_limited = _all_execution_limited()
    hud_result = {"file": "templates/jarvis/mobile_control_center.html", "exists": HUD_FILE.exists(), "markers_present": False, "state": "missing", "ok": False}
    if HUD_FILE.exists():
        text = HUD_FILE.read_text(encoding="utf-8", errors="replace")
        missing = [marker for marker in HUD_MARKERS if marker not in text]
        hud_result["missing_markers"] = missing
        hud_result["markers_present"] = not missing
        hud_result["state"] = "complete" if not missing else "incomplete"
        hud_result["ok"] = not missing
    layers["layer_8_controlled_execution_hud"] = hud_result
    all_ok = all_ok and hud_result["ok"] and rollback_ok and execution_limited

    return {
        "phase": "Phase 13 - Controlled Autonomous Execution",
        "probe": "Validation + Probes",
        "ok": all_ok,
        "execution": "Limited Sandbox Only",
        "execution_limited": execution_limited,
        "database_mutation": False,
        "deploy": False,
        "rollback_for_every_execution": rollback_ok,
        "autonomous_apply_off": True,
        "human_approval_required": True,
        "bounded_and_safe": all_ok,
        "layers": layers,
    }


if __name__ == "__main__":
    print(json.dumps(probe_phase13(), ensure_ascii=False, indent=2))
