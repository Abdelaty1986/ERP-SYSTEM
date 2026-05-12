from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from jarvis.execution.runtime_wake_supervisor import RuntimeWakeSupervisor
from jarvis.memory.runtime_observation_memory import RuntimeObservationMemory


LOG_DIR = Path("JARVIS_CORE/runtime_logs")
CYCLE_FILE = LOG_DIR / "runtime_wake_cycles.jsonl"


class RuntimeWakeCycle:
    """
    Safe bounded runtime wake cognition cycle.

    This cycle:
    - observes
    - emits cognition telemetry
    - records wake/sleep transitions

    It does NOT:
    - execute shell commands
    - apply patches
    - perform autonomous repair
    """

    def __init__(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.supervisor = RuntimeWakeSupervisor()
        self.memory = RuntimeObservationMemory()

    def iso_now(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def append_event(self, payload: Dict[str, Any]) -> None:
        with CYCLE_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def run_cycle(self) -> Dict[str, Any]:
        supervisor_result = self.supervisor.tick()

        wake_needed = supervisor_result.get("wake_needed", False)

        cycle_state = "wake_cycle_active" if wake_needed else "observe_and_sleep"

        cognition_event = {
            "timestamp": self.iso_now(),
            "cycle_state": cycle_state,
            "source": "runtime_wake_cycle",
            "reasoning": (
                "Runtime silence detected; bounded wake cognition cycle activated"
                if wake_needed
                else "Runtime healthy; observation cycle completed"
            ),
            "wake_needed": wake_needed,
            "supervisor_event_type": supervisor_result.get("event_type"),
            "safety": {
                "shell_execution": False,
                "patch_apply": False,
                "auto_repair": False,
                "bounded": True,
            },
        }

        self.append_event(cognition_event)
        memory_result = self.memory.remember_cycle(cognition_event)

        return {
            "processed": True,
            "cycle_state": cycle_state,
            "wake_needed": wake_needed,
            "supervisor_event_type": supervisor_result.get("event_type"),
            "cycle_file": str(CYCLE_FILE),
            "memory": memory_result,
        }


def main() -> None:
    result = RuntimeWakeCycle().run_cycle()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
