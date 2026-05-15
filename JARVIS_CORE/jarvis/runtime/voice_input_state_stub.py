import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "voice_input_state_stub.json"
LOG_PATH = LOGS_DIR / "voice_input_state_stub.jsonl"


class VoiceInputStateStub:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "voice_input_state_stub",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "microphone_enabled": False,
            "voice_command_execution_allowed": False,
            "phase": "phase_7_voice_runtime",
            "layer": "voice_input_state_stub",
            "input_mode": "simulated_voice_input_only",
            "voice_input": {
                "state": "stub_ready",
                "microphone_access_requested": False,
                "audio_recording_enabled": False,
                "live_stream_active": False,
                "last_transcript": None,
                "simulated_transcript": "JARVIS voice input simulation ready.",
            },
            "prohibited_actions": [
                "microphone_activation",
                "audio_recording",
                "background_listening",
                "live_voice_command_execution",
            ],
            "result": "voice_input_state_stub_built",
        }
        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "state": result["voice_input"]["state"],
            "microphone_enabled": False,
            "voice_command_execution_allowed": False,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(VoiceInputStateStub().build(), ensure_ascii=False, indent=2))
