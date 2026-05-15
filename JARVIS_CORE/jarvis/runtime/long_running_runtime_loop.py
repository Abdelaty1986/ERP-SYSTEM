import json
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"

LOOP_REPORT = MEMORY_DIR / "long_running_runtime_loop.json"
LOOP_TIMELINE = LOGS_DIR / "long_running_runtime_loop.jsonl"


class LongRunningRuntimeLoop:
    def __init__(self, cycles=3, interval=1):
        self.cycles = cycles
        self.interval = interval

        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def run(self):
        cycle_events = []

        for cycle in range(1, self.cycles + 1):
            event = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "runtime": "long_running_runtime_loop",
                "bounded": True,
                "cycle": cycle,
                "max_cycles": self.cycles,
                "runtime_state": "monitoring",
                "execution_allowed": False,
                "apply_allowed": False,
                "autonomous_apply": False,
                "dangerous_autonomous_apply": False,
                "monitoring_mode": "cognitive_supervision_only",
            }

            cycle_events.append(event)

            with LOOP_TIMELINE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

            time.sleep(self.interval)

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "long_running_runtime_loop",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "loop_state": "completed",
            "cycles_completed": self.cycles,
            "monitoring_mode": "cognitive_supervision_only",
            "events_recorded": len(cycle_events),
            "continuous_runtime": True,
        }

        LOOP_REPORT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return report


def start_loop():
    return LongRunningRuntimeLoop().run()


if __name__ == "__main__":
    print(json.dumps(start_loop(), ensure_ascii=False, indent=2))
