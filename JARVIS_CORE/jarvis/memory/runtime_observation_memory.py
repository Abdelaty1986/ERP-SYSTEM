from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List


LOG_DIR = Path("JARVIS_CORE/runtime_logs")
MEMORY_FILE = LOG_DIR / "runtime_observation_memory.json"


class RuntimeObservationMemory:
    """
    Safe bounded runtime observation memory.

    Stores:
    - wake history
    - cognition states
    - silence observations
    - supervisor summaries

    Does NOT:
    - execute actions
    - apply patches
    - make autonomous decisions
    """

    MAX_HISTORY = 25

    def __init__(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def iso_now(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def load_memory(self) -> Dict[str, Any]:
        if not MEMORY_FILE.exists():
            return {
                "created_at": self.iso_now(),
                "wake_history": [],
                "silence_history": [],
                "cognition_history": [],
                "supervisor_history": [],
            }

        try:
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {
                "created_at": self.iso_now(),
                "wake_history": [],
                "silence_history": [],
                "cognition_history": [],
                "supervisor_history": [],
            }

    def save_memory(self, memory: Dict[str, Any]) -> None:
        MEMORY_FILE.write_text(
            json.dumps(memory, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def trim_history(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return items[-self.MAX_HISTORY:]

    def remember_cycle(self, cycle: Dict[str, Any]) -> Dict[str, Any]:
        memory = self.load_memory()

        wake_entry = {
            "timestamp": self.iso_now(),
            "wake_needed": cycle.get("wake_needed"),
            "cycle_state": cycle.get("cycle_state"),
        }

        silence_entry = {
            "timestamp": self.iso_now(),
            "silence_detected": cycle.get("silence_detected", True),
        }

        cognition_entry = {
            "timestamp": self.iso_now(),
            "reasoning": cycle.get("reasoning"),
            "cycle_state": cycle.get("cycle_state"),
        }

        supervisor_entry = {
            "timestamp": self.iso_now(),
            "supervisor_event_type": cycle.get("supervisor_event_type"),
        }

        memory["wake_history"].append(wake_entry)
        memory["silence_history"].append(silence_entry)
        memory["cognition_history"].append(cognition_entry)
        memory["supervisor_history"].append(supervisor_entry)

        memory["wake_history"] = self.trim_history(memory["wake_history"])
        memory["silence_history"] = self.trim_history(memory["silence_history"])
        memory["cognition_history"] = self.trim_history(memory["cognition_history"])
        memory["supervisor_history"] = self.trim_history(memory["supervisor_history"])

        memory["last_updated"] = self.iso_now()

        self.save_memory(memory)

        return {
            "stored": True,
            "wake_history_size": len(memory["wake_history"]),
            "cognition_history_size": len(memory["cognition_history"]),
            "memory_file": str(MEMORY_FILE),
        }


def main() -> None:
    sample_cycle = {
        "wake_needed": True,
        "cycle_state": "wake_cycle_active",
        "reasoning": "Runtime silence detected",
        "supervisor_event_type": "wake_signal",
        "silence_detected": True,
    }

    result = RuntimeObservationMemory().remember_cycle(sample_cycle)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
