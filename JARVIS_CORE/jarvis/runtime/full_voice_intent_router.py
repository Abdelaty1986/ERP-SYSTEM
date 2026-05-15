import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
JARVIS_ROOT = PROJECT_ROOT / "JARVIS_CORE"
for import_path in (PROJECT_ROOT, JARVIS_ROOT):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from JARVIS_CORE.jarvis.runtime.full_voice_safety_guard import (
    SAFETY_CONTRACT,
    evaluate_voice_safety,
)
from JARVIS_CORE.jarvis.runtime.runtime_governance_decision import assess_risk
from JARVIS_CORE.jarvis.runtime.runtime_intent_pipeline import classify_intent


RUNTIME_MEMORY = PROJECT_ROOT / "JARVIS_CORE" / "runtime_memory"

INVENTORY_FILE = RUNTIME_MEMORY / "full_voice_system_inventory.json"
TTS_CONFIG_FILE = RUNTIME_MEMORY / "professional_voice_output_config.json"
VOICE_MEMORY_FILE = RUNTIME_MEMORY / "voice_conversation_memory.json"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _write_json(path, payload):
    RUNTIME_MEMORY.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _safe_load_json(path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def build_voice_system_inventory():
    voice_paths = []
    for base in [PROJECT_ROOT / "JARVIS_CORE" / "jarvis", PROJECT_ROOT / "templates" / "jarvis"]:
        if not base.exists():
            continue
        for item in base.rglob("*"):
            if not item.is_file():
                continue
            rel = item.relative_to(PROJECT_ROOT).as_posix()
            if "voice" in item.name.lower() or item.suffix.lower() in {".html", ".py"} and "voice" in item.read_text(encoding="utf-8", errors="replace").lower():
                voice_paths.append(rel)

    inventory = {
        "phase": "Phase 14 - Full Voice Conversation Runtime",
        "layer": "Layer 1 - Voice System Audit",
        "generated_at": _now(),
        "state": "operational",
        "safety": SAFETY_CONTRACT,
        "voice_files_detected": sorted(set(voice_paths)),
        "browser_voice_capabilities": {
            "speech_recognition": "provided_by_browser_when_available",
            "speech_synthesis": "provided_by_browser_when_available",
            "server_side_audio_capture": False,
        },
        "routes": {
            "voice_command": "/jarvis/mobile/api/voice/command",
            "method": "POST",
            "executes_dangerous_actions": False,
        },
    }
    _write_json(INVENTORY_FILE, inventory)
    return inventory


def build_professional_voice_output_config():
    config = {
        "phase": "Phase 14 - Full Voice Conversation Runtime",
        "layer": "Layer 6 - Professional Voice Output",
        "generated_at": _now(),
        "state": "operational",
        "safety": SAFETY_CONTRACT,
        "browser_speech_synthesis_first": True,
        "voice_selection_preference": [
            "male English voice",
            "male Arabic voice",
            "best available English voice",
            "best available Arabic voice",
            "browser default voice",
        ],
        "future_tts_providers": {
            "elevenlabs": {"enabled": False, "api_key_required": True},
            "openai_tts": {"enabled": False, "api_key_required": True},
        },
        "requires_api_key_now": False,
    }
    _write_json(TTS_CONFIG_FILE, config)
    return config


def write_voice_memory(command="", response="", voice_state="idle", approval_required=False, blocked_reason=None):
    memory = {
        "phase": "Phase 14 - Full Voice Conversation Runtime",
        "layer": "Layer 7 - Voice Conversation Memory",
        "timestamp": _now(),
        "state": "operational",
        "bounded": True,
        "safety": SAFETY_CONTRACT,
        "last_voice_command": command,
        "last_text_response": response,
        "voice_state": voice_state,
        "approval_required": approval_required,
        "blocked_reason": blocked_reason,
    }
    _write_json(VOICE_MEMORY_FILE, memory)
    return memory


def initialize_phase14():
    inventory = build_voice_system_inventory()
    config = build_professional_voice_output_config()
    if not VOICE_MEMORY_FILE.exists():
        write_voice_memory()
    return {
        "phase": "Phase 14 - Full Voice Conversation Runtime",
        "state": "operational",
        "inventory": inventory["state"],
        "tts_config": config["state"],
        "voice_memory": "operational",
        "safety": SAFETY_CONTRACT,
    }


def _load_simulation_summary():
    matrix = _safe_load_json(RUNTIME_MEMORY / "simulation_decision_matrix.json") or {}
    readiness = _safe_load_json(RUNTIME_MEMORY / "simulation_readiness_report.json") or {}
    return {
        "safe_to_execute_false": matrix.get("all_safe_to_execute_false"),
        "simulation_readiness": readiness.get("readiness_state", "unknown"),
    }


def _response_for(intent, safety):
    if safety["state"] == "blocked":
        return "I blocked that voice command because it touches a dangerous or restricted action. Human review is required before anything risky can proceed."
    if safety["state"] == "approval_required":
        return "That request may change the system, so I cannot execute it by voice. I can prepare a safe plan for human review."
    if intent.get("classified_intent") == "report":
        return "JARVIS is online. Voice routing is operational, governance is active, and dangerous actions are blocked."
    if intent.get("classified_intent") == "testing":
        return "I can help plan safe validation steps. Voice commands will not run tests or execution paths without approval."
    if intent.get("classified_intent") in {"analysis", "improvement"}:
        return "I can analyze that request and suggest a governed plan. Any implementation still requires human approval."
    return "I heard you. I routed the command through JARVIS safety and governance. This voice layer can respond and plan, but it will not execute risky work."


def route_voice_command(recognized_text):
    initialize_phase14()
    text = (recognized_text or "").strip()
    safety = evaluate_voice_safety(text)
    classified_intent = classify_intent(text)
    risk = assess_risk(text)
    simulation = _load_simulation_summary()
    response = _response_for({"classified_intent": classified_intent}, safety)
    voice_state = "blocked" if safety["state"] == "blocked" else "approval_required" if safety["approval_required"] else "speaking"
    memory = write_voice_memory(
        command=text,
        response=response,
        voice_state=voice_state,
        approval_required=safety["approval_required"],
        blocked_reason=safety["blocked_reason"],
    )
    return {
        "state": "operational",
        "recognized_text": text,
        "structured_intent": {
            "intent_id": "voice_preview_intent",
            "classified_intent": classified_intent,
            "execution_mode": "simulation_only",
            "execution_allowed": False,
        },
        "governance": {
            "risk_level": risk.get("risk_level"),
            "approval_gate": risk.get("approval_gate"),
            "execution_allowed": False,
            "autonomous_apply_allowed": False,
        },
        "safety": safety,
        "simulation": simulation,
        "text_response": response,
        "approval_state": "approval_required" if safety["approval_required"] else "not_required",
        "voice_state": memory["voice_state"],
    }


if __name__ == "__main__":
    print(json.dumps(initialize_phase14(), ensure_ascii=False, indent=2))
