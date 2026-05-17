import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "wake_word_readiness_state.json"
LOG_PATH = LOGS_DIR / "wake_word_readiness_state.jsonl"


class WakeWordReadinessState:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "wake_word_readiness_state",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "microphone_enabled": False,
            "voice_command_execution_allowed": False,
            "phase": "phase_7_voice_runtime",
            "layer": "wake_word_readiness_state",
            "readiness_mode": "simulated_wake_word_monitoring_only",
            "wake_word": {
                "configured_phrase": "Jarvis",
                "readiness_state": "simulation_ready",
                "listener_enabled": False,
                "background_listener_active": False,
                "microphone_listening": False,
                "last_detected_at": None,
                "detection_mode": "manual_future_approval_required",
            },
            "prohibited_actions": [
                "wake_word_background_listener",
                "microphone_listening",
                "audio_stream_analysis",
                "automatic_command_unlock",
            ],
            "result": "wake_word_readiness_state_built",
        }
        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "readiness_state": result["wake_word"]["readiness_state"],
            "listener_enabled": False,
            "microphone_enabled": False,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(WakeWordReadinessState().build(), ensure_ascii=False, indent=2))
