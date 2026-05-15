import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "voice_command_intent_queue.json"
LOG_PATH = LOGS_DIR / "voice_command_intent_queue.jsonl"


class VoiceCommandIntentQueue:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        now = datetime.now(timezone.utc).isoformat()
        intents = [
            {
                "intent_id": "voice-intent-preview-status",
                "source": "simulated_voice_runtime",
                "transcript": "Jarvis, show runtime status.",
                "intent_type": "runtime_status_request",
                "queue_state": "awaiting_human_approval",
                "execution_allowed": False,
                "requires_human_approval": True,
                "created_at": now,
            }
        ]
        result = {
            "timestamp": now,
            "runtime": "voice_command_intent_queue",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "microphone_enabled": False,
            "voice_command_execution_allowed": False,
            "phase": "phase_7_voice_runtime",
            "layer": "voice_command_intent_queue",
            "queue_mode": "safe_simulated_voice_intents_only",
            "intent_count": len(intents),
            "pending_approval_count": len(intents),
            "intents": intents,
            "queue_policy": {
                "execute_from_queue": False,
                "auto_dequeue": False,
                "human_approval_required_for_all": True,
                "dangerous_intents_blocked_by_default": True,
            },
            "result": "voice_command_intent_queue_built",
        }
        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "intent_count": result["intent_count"],
            "pending_approval_count": result["pending_approval_count"],
            "voice_command_execution_allowed": False,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(VoiceCommandIntentQueue().build(), ensure_ascii=False, indent=2))
