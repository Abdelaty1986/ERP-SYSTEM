import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "voice_safety_gate.json"
LOG_PATH = LOGS_DIR / "voice_safety_gate.jsonl"
QUEUE_PATH = MEMORY_DIR / "voice_command_intent_queue.json"

DANGEROUS_TERMS = {
    "delete",
    "drop",
    "deploy",
    "push",
    "merge",
    "reset",
    "format",
    "execute",
    "apply",
}


def load_queue():
    if not QUEUE_PATH.exists():
        return {}
    try:
        return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


class VoiceSafetyGate:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        queue = load_queue()
        evaluated = []
        for intent in queue.get("intents", []):
            transcript = (intent.get("transcript") or "").lower()
            matched_terms = sorted(term for term in DANGEROUS_TERMS if term in transcript)
            evaluated.append({
                "intent_id": intent.get("intent_id"),
                "intent_type": intent.get("intent_type"),
                "queue_state": intent.get("queue_state"),
                "dangerous_terms": matched_terms,
                "safety_decision": "blocked_pending_human_review",
                "execution_allowed": False,
                "requires_human_approval": True,
            })

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "voice_safety_gate",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "microphone_enabled": False,
            "voice_command_execution_allowed": False,
            "phase": "phase_7_voice_runtime",
            "layer": "voice_safety_gate",
            "gate_mode": "block_by_default_voice_intent_review",
            "intent_count": len(evaluated),
            "evaluated_intents": evaluated,
            "gate_policy": {
                "default_decision": "blocked_pending_human_review",
                "execute_safe_intents_automatically": False,
                "execute_dangerous_intents": False,
                "human_approval_required": True,
                "microphone_can_unlock_gate": False,
            },
            "result": "voice_safety_gate_built",
        }
        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "intent_count": result["intent_count"],
            "default_decision": result["gate_policy"]["default_decision"],
            "voice_command_execution_allowed": False,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(VoiceSafetyGate().build(), ensure_ascii=False, indent=2))
