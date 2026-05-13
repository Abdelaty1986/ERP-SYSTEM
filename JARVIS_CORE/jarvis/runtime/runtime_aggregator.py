from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


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

    def aggregate(self):
        aggregated = {}

        for name, path in self.sources.items():
            aggregated[name] = self._load_json(path)

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
