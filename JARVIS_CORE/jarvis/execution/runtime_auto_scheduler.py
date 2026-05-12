from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from jarvis.execution.runtime_queue_worker import RuntimeQueueWorker
from jarvis.execution.runtime_timeline import RuntimeTimeline


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class RuntimeAutoScheduler:
    """
    Safe runtime scheduler v1:
    - manual start only
    - bounded ticks by default
    - no daemon/background mode yet
    - uses RuntimeQueueWorker.process_once()
    - keeps idle heartbeat alive through the worker
    """

    def __init__(self, interval_seconds: float = 2.0, max_ticks: int = 3):
        self.interval_seconds = interval_seconds
        self.max_ticks = max_ticks
        self.worker = RuntimeQueueWorker()
        self.timeline = RuntimeTimeline()

    def run(self) -> Dict[str, Any]:
        session_id = "scheduler-" + utc_now().replace(":", "").replace("-", "")

        results: List[Dict[str, Any]] = []

        self.timeline.add_event(
            session_id=session_id,
            stage="scheduler_start",
            agent_id="runtime_auto_scheduler",
            status="started",
            message="Runtime auto scheduler started in bounded safe mode",
            payload={
                "interval_seconds": self.interval_seconds,
                "max_ticks": self.max_ticks,
                "mode": "manual_bounded",
            },
        )

        for tick_index in range(1, self.max_ticks + 1):
            tick_started_at = utc_now()
            result = self.worker.process_once()

            tick_result = {
                "tick": tick_index,
                "timestamp": tick_started_at,
                "result": result,
            }
            results.append(tick_result)

            self.timeline.add_event(
                session_id=session_id,
                stage="scheduler_tick",
                agent_id="runtime_auto_scheduler",
                status="completed" if result.get("processed") else "idle",
                message="Runtime scheduler tick completed",
                payload=tick_result,
            )

            if tick_index < self.max_ticks:
                time.sleep(self.interval_seconds)

        summary = {
            "session_id": session_id,
            "status": "completed",
            "mode": "manual_bounded",
            "ticks": len(results),
            "processed_count": len([r for r in results if r["result"].get("processed")]),
            "idle_count": len([r for r in results if not r["result"].get("processed")]),
            "results": results,
        }

        self.timeline.add_event(
            session_id=session_id,
            stage="scheduler_completed",
            agent_id="runtime_auto_scheduler",
            status="completed",
            message="Runtime auto scheduler completed bounded run",
            payload=summary,
        )

        return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run JARVIS runtime auto scheduler in bounded safe mode.")
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--max-ticks", type=int, default=3)
    args = parser.parse_args()

    scheduler = RuntimeAutoScheduler(
        interval_seconds=args.interval,
        max_ticks=args.max_ticks,
    )

    print(json.dumps(scheduler.run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
