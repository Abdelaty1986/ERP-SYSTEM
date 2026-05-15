import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "voice_output_state_stub.json"
LOG_PATH = LOGS_DIR / "voice_output_state_stub.jsonl"


class VoiceOutputStateStub:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "voice_output_state_stub",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "microphone_enabled": False,
            "voice_command_execution_allowed": False,
            "phase": "phase_7_voice_runtime",
            "layer": "voice_output_state_stub",
            "output_mode": "simulated_voice_output_only",
            "voice_output": {
                "state": "stub_ready",
                "tts_engine_enabled": False,
                "audio_playback_enabled": False,
                "speaker_output_active": False,
                "last_spoken_text": None,
                "simulated_response": "JARVIS voice output simulation ready.",
            },
            "prohibited_actions": [
                "tts_engine_activation",
                "audio_playback",
                "speaker_output",
                "live_voice_response_execution",
            ],
            "result": "voice_output_state_stub_built",
        }
        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "state": result["voice_output"]["state"],
            "audio_playback_enabled": False,
            "voice_command_execution_allowed": False,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(VoiceOutputStateStub().build(), ensure_ascii=False, indent=2))
