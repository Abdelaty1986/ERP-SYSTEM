import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
JARVIS_ROOT = PROJECT_ROOT / "JARVIS_CORE"
for import_path in (PROJECT_ROOT, JARVIS_ROOT):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from JARVIS_CORE.jarvis.runtime.full_voice_intent_router import (
    INVENTORY_FILE,
    TTS_CONFIG_FILE,
    VOICE_MEMORY_FILE,
    initialize_phase14,
    route_voice_command,
)
from JARVIS_CORE.jarvis.runtime.full_voice_safety_guard import evaluate_voice_safety


def _load(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def probe_phase14():
    initialize_phase14()
    safe_result = route_voice_command("Jarvis, give me a system status report")
    blocked_result = route_voice_command("Jarvis, deploy and delete the database")
    guard_result = evaluate_voice_safety("delete database")

    checks = {
        "inventory_exists": INVENTORY_FILE.exists(),
        "tts_config_exists": TTS_CONFIG_FILE.exists(),
        "voice_memory_exists": VOICE_MEMORY_FILE.exists(),
        "safe_routing_operational": safe_result.get("state") == "operational",
        "safe_response_generated": bool(safe_result.get("text_response")),
        "dangerous_command_blocked": blocked_result.get("voice_state") == "blocked",
        "safety_guard_blocks_risky_commands": guard_result.get("state") == "blocked",
        "memory_state_operational": _load(VOICE_MEMORY_FILE).get("state") == "operational",
    }
    ok = all(checks.values())
    return {
        "phase": "Phase 14 - Full Voice Conversation Runtime",
        "state": "operational" if ok else "warning",
        "ok": ok,
        "checks": checks,
        "safe_route_sample": {
            "intent": safe_result.get("structured_intent", {}).get("classified_intent"),
            "approval_state": safe_result.get("approval_state"),
            "voice_state": safe_result.get("voice_state"),
        },
        "blocked_route_sample": {
            "approval_state": blocked_result.get("approval_state"),
            "voice_state": blocked_result.get("voice_state"),
            "blocked_reason": blocked_result.get("safety", {}).get("blocked_reason"),
        },
    }


if __name__ == "__main__":
    print(json.dumps(probe_phase14(), ensure_ascii=False, indent=2))
