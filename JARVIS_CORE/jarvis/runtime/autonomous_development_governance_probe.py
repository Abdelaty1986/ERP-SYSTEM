import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_MEMORY = PROJECT_ROOT / "JARVIS_CORE" / "runtime_memory"
HUD_FILE = PROJECT_ROOT / "templates" / "jarvis" / "mobile_control_center.html"

EXPECTED_FILES = {
    "layer_1_governance_inventory": "development_governance_inventory.json",
    "layer_2_request_classifier": "development_request_classifier.json",
    "layer_3_policy_engine": "governance_policy_engine.json",
    "layer_4_approval_escalation": "approval_escalation_matrix.json",
    "layer_5_consistency_check": "cross_runtime_consistency_check.json",
    "layer_6_readiness": "autonomous_development_readiness.json",
    "layer_7_decision_simulator": "governance_decision_simulator.json",
}

EXPECTED_SAFETY = {
    "bounded": True,
    "analysis_only": True,
    "execution_allowed": False,
    "apply_allowed": False,
    "autonomous_apply": False,
    "database_mutation_allowed": False,
    "deploy_allowed": False,
    "human_approval_required": True,
}

HUD_MARKERS = [
    "phase10-development-governance-panel",
    "Governance Inventory",
    "Policy Engine",
    "Approval Escalation",
    "Consistency State",
    "Readiness State",
    "Simulator State",
    "execution=No",
    "database_mutation=No",
    "autonomous_apply=Off",
    "human_approval=Yes",
]


def _load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def probe_phase10():
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
        result["ok"] = (
            result["exists"]
            and result["valid_json"]
            and result["state"] == "complete"
            and result["safety_ok"]
        )
        all_ok = all_ok and result["ok"]
        layers[layer_name] = result

    hud_result = {
        "file": "templates/jarvis/mobile_control_center.html",
        "exists": HUD_FILE.exists(),
        "markers_present": False,
        "state": "missing",
        "ok": False,
    }
    if HUD_FILE.exists():
        text = HUD_FILE.read_text(encoding="utf-8", errors="replace")
        missing = [marker for marker in HUD_MARKERS if marker not in text]
        hud_result["missing_markers"] = missing
        hud_result["markers_present"] = not missing
        hud_result["state"] = "complete" if not missing else "incomplete"
        hud_result["ok"] = not missing
    all_ok = all_ok and hud_result["ok"]
    layers["layer_8_development_governance_hud"] = hud_result

    return {
        "phase": "Phase 10 - Autonomous Development Governance",
        "probe": "Validation + Probes",
        "ok": all_ok,
        "execution_or_apply": False,
        "database_mutation": False,
        "deploy": False,
        "autonomous_apply_off": True,
        "human_approval_required": True,
        "bounded_and_safe": all_ok,
        "layers": layers,
    }


if __name__ == "__main__":
    print(json.dumps(probe_phase10(), ensure_ascii=False, indent=2))
