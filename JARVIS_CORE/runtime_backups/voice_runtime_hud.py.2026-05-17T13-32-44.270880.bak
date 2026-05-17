import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "voice_runtime_hud.json"
LOG_PATH = LOGS_DIR / "voice_runtime_hud.jsonl"

SOURCES = {
    "input": "voice_input_state_stub.json",
    "output": "voice_output_state_stub.json",
    "wake_word": "wake_word_readiness_state.json",
    "intent_queue": "voice_command_intent_queue.json",
    "safety_gate": "voice_safety_gate.json",
}


def load_json(name):
    path = MEMORY_DIR / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class VoiceRuntimeHud:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        sources = {name: load_json(filename) for name, filename in SOURCES.items()}
        queue = sources["intent_queue"]
        gate = sources["safety_gate"]

        hud = {
            "title": "Voice Runtime",
            "phase": "Phase 7",
            "status": "locked_simulation_ready",
            "monitoring_only": True,
            "microphone_enabled": False,
            "voice_command_execution_allowed": False,
            "sections": {
                "input": {
                    "state": sources["input"].get("voice_input", {}).get("state"),
                    "microphone_access_requested": sources["input"].get("voice_input", {}).get("microphone_access_requested", False),
                    "audio_recording_enabled": sources["input"].get("voice_input", {}).get("audio_recording_enabled", False),
                },
                "output": {
                    "state": sources["output"].get("voice_output", {}).get("state"),
                    "tts_engine_enabled": sources["output"].get("voice_output", {}).get("tts_engine_enabled", False),
                    "audio_playback_enabled": sources["output"].get("voice_output", {}).get("audio_playback_enabled", False),
                },
                "wake_word": {
                    "state": sources["wake_word"].get("wake_word", {}).get("readiness_state"),
                    "listener_enabled": sources["wake_word"].get("wake_word", {}).get("listener_enabled", False),
                    "microphone_listening": sources["wake_word"].get("wake_word", {}).get("microphone_listening", False),
                },
                "intent_queue": {
                    "intent_count": queue.get("intent_count", 0),
                    "pending_approval_count": queue.get("pending_approval_count", 0),
                    "execute_from_queue": queue.get("queue_policy", {}).get("execute_from_queue", False),
                },
                "safety_gate": {
                    "intent_count": gate.get("intent_count", 0),
                    "default_decision": gate.get("gate_policy", {}).get("default_decision"),
                    "execute_safe_intents_automatically": gate.get("gate_policy", {}).get("execute_safe_intents_automatically", False),
                },
            },
            "locks": {
                "bounded": True,
                "execution_allowed": False,
                "apply_allowed": False,
                "autonomous_apply": False,
                "dangerous_autonomous_apply": False,
                "human_approval_required": True,
                "microphone_enabled": False,
                "voice_command_execution_allowed": False,
                "audio_recording_enabled": False,
                "audio_playback_enabled": False,
                "wake_word_listener_enabled": False,
            },
            "warnings": [
                "voice_runtime_is_simulation_only",
                "voice_intents_require_human_approval",
                "voice_command_execution_locked",
            ],
        }

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "voice_runtime_hud",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "microphone_enabled": False,
            "voice_command_execution_allowed": False,
            "phase": "phase_7_voice_runtime",
            "layer": "voice_runtime_hud",
            "hud_mode": "safe_read_only_voice_runtime_visibility",
            "hud": hud,
            "source_count": len([data for data in sources.values() if data]),
            "recommendation": "phase_7_complete_continue_to_autonomous_erp_evolution",
            "result": "voice_runtime_hud_built",
        }
        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "status": result["hud"]["status"],
            "source_count": result["source_count"],
            "microphone_enabled": False,
            "voice_command_execution_allowed": False,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(VoiceRuntimeHud().build(), ensure_ascii=False, indent=2))
