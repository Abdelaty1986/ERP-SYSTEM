from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from jarvis.runtime.agent_skill_memory import (
    build_agent_skill_snapshot,
)
from jarvis.runtime.runtime_audit import RuntimeAudit


class RuntimeAggregator:
    def __init__(self, root: str = "JARVIS_CORE"):
        self.root = Path(root)

        self.sources = {
            "approval_gateway":
                self.root / "runtime_memory" / "approval_gateway.json",

            "approval_lineage":
                self.root / "runtime_memory" / "approval_lineage.json",

            "approval_transition":
                self.root / "runtime_memory" / "approval_transitions.json",

            "execution_journal":
                self.root / "runtime_memory" / "execution_journal.json",

            "safe_execution_queue":
                self.root / "runtime_memory" / "safe_execution_queue.json",

            "agent_skill_memory":
                self.root / "runtime_memory" / "agent_skill_memory.json",

            "agent_routing_memory":
                self.root / "runtime_memory" / "agent_routing_memory.json",

            "task_chain_memory":
                self.root / "runtime_memory" / "task_chain_memory.json",

            "task_execution_simulation":
                self.root / "runtime_memory" / "task_execution_simulation.json",

            "rollback_checkpoint_memory":
                self.root / "runtime_memory" / "rollback_checkpoint_memory.json",

            "controlled_apply_decision":
                self.root / "runtime_memory" / "controlled_apply_decision.json",

            "human_approved_apply":
                self.root / "runtime_memory" / "human_approved_apply.json",

            "learning_summary":
                self.root / "runtime_memory" / "learning_summary.json",

            "failure_summary":
                self.root / "runtime_memory" / "failure_summary.json",
        }

        self.output_file = (
            self.root / "runtime_logs" / "runtime_aggregation_snapshot.json"
        )

    def _load_json(self, path: Path):
        if not path.exists():
            return {
                "exists": False,
                "data": {}
            }

        try:
            return {
                "exists": True,
                "data": json.loads(path.read_text(encoding="utf-8"))
            }
        except Exception:
            return {
                "exists": True,
                "corrupted": True,
                "data": {}
            }

    def _load_latest_sandbox_report(self):
        reports_dir = (
            self.root / "runtime_logs" / "sandbox_execution_reports"
        )

        if not reports_dir.exists():
            return {
                "exists": False,
                "data": {},
                "reason": "no_sandbox_reports"
            }

        reports = sorted(
            reports_dir.glob("*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )

        if not reports:
            return {
                "exists": False,
                "data": {},
                "reason": "empty_sandbox_reports"
            }

        latest = self._load_json(reports[0])
        latest["latest_report_file"] = str(reports[0])
        return latest

    def aggregate(self):
        aggregated = {}

        for name, path in self.sources.items():
            aggregated[name] = self._load_json(path)

        aggregated["agent_skill_snapshot"] = {
            "exists": True,
            "data": build_agent_skill_snapshot()
        }

        aggregated["runtime_audit"] = {
            "exists": True,
            "data": RuntimeAudit(root=str(self.root)).run()
        }

        aggregated["latest_sandbox_execution_report"] = (
            self._load_latest_sandbox_report()
        )

        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "aggregator": "runtime_aggregator",
            "bounded": True,
            "real_apply_enabled": False,
            "autonomous_apply": False,
            "execution_unlock_allowed": False,
            "runtime_count": len(aggregated),
            "aggregation_state": "stable",
            "aggregated_runtimes": aggregated,
        }

        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        self.output_file.write_text(
            json.dumps(snapshot, indent=2),
            encoding="utf-8"
        )

        return snapshot


if __name__ == "__main__":
    print(json.dumps(RuntimeAggregator().aggregate(), indent=2))
