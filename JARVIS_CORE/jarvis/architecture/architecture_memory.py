from pathlib import Path
from datetime import datetime
import json

class ArchitectureMemory:
    def __init__(self, root="."):
        self.root = Path(root)
        self.memory_dir = self.root / "JARVIS_CORE" / "runtime_logs"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.memory_file = self.memory_dir / "architecture_memory.jsonl"

    def record_snapshot(self, hotspot_data, priority_data, dependency_data):
        snapshot = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "bounded": True,
            "mode": "persistent_observation_memory",
            "autonomous_apply": False,
            "hotspots_summary": hotspot_data.get("summary", {}),
            "priority_summary": priority_data.get("summary", {}),
            "dependency_summary": dependency_data.get("summary", {}),
            "top_hotspot": self._first_file(hotspot_data.get("top_hotspots", [])),
            "top_priority": self._first_file(priority_data.get("priorities", [])),
            "top_dependency_risk": self._first_file(dependency_data.get("dependency_reasoning", [])),
        }

        with self.memory_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")

        return self.build_evolution_report()

    def build_evolution_report(self, limit=20):
        snapshots = self._read_snapshots(limit)

        if not snapshots:
            return self._empty_report()

        latest = snapshots[-1]
        previous = snapshots[-2] if len(snapshots) >= 2 else None

        return {
            "bounded": True,
            "mode": "persistent_observation_memory",
            "autonomous_apply": False,
            "summary": {
                "snapshots_recorded": len(snapshots),
                "memory_file": str(self.memory_file),
                "latest_timestamp": latest.get("timestamp"),
            },
            "latest": latest,
            "evolution": self._compare(previous, latest),
            "notes": [
                "Architecture memory stores observation snapshots only.",
                "No source files are modified by this memory engine.",
                "Evolution analysis becomes stronger after multiple snapshots."
            ],
        }

    def _read_snapshots(self, limit):
        if not self.memory_file.exists():
            return []

        rows = []
        for line in self.memory_file.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:
                continue

        return rows[-limit:]

    def _compare(self, previous, latest):
        if not previous:
            return {
                "state": "initial_snapshot",
                "message": "No previous architecture memory snapshot available yet.",
                "hotspot_delta": 0,
                "critical_delta": 0,
                "cascade_delta": 0,
            }

        prev_hotspots = previous.get("hotspots_summary", {}).get("hotspots_found", 0)
        now_hotspots = latest.get("hotspots_summary", {}).get("hotspots_found", 0)

        prev_critical = previous.get("priority_summary", {}).get("critical", 0)
        now_critical = latest.get("priority_summary", {}).get("critical", 0)

        prev_high_cascade = previous.get("dependency_summary", {}).get("high_cascade", 0)
        now_high_cascade = latest.get("dependency_summary", {}).get("high_cascade", 0)

        return {
            "state": "compared",
            "hotspot_delta": now_hotspots - prev_hotspots,
            "critical_delta": now_critical - prev_critical,
            "cascade_delta": now_high_cascade - prev_high_cascade,
            "message": self._evolution_message(
                now_hotspots - prev_hotspots,
                now_critical - prev_critical,
                now_high_cascade - prev_high_cascade
            ),
        }

    def _evolution_message(self, hotspot_delta, critical_delta, cascade_delta):
        if hotspot_delta > 0 or critical_delta > 0 or cascade_delta > 0:
            return "Architecture risk increased compared with previous snapshot."
        if hotspot_delta < 0 or critical_delta < 0 or cascade_delta < 0:
            return "Architecture risk decreased compared with previous snapshot."
        return "Architecture risk appears stable compared with previous snapshot."

    def _first_file(self, items):
        if not items:
            return None
        item = items[0]
        return {
            "file": item.get("file"),
            "risk": item.get("risk") or item.get("cascade_risk") or item.get("priority"),
            "score": item.get("hotspot_score") or item.get("priority_score"),
        }

    def _empty_report(self):
        return {
            "bounded": True,
            "mode": "persistent_observation_memory",
            "autonomous_apply": False,
            "summary": {
                "snapshots_recorded": 0,
                "memory_file": str(self.memory_file),
            },
            "latest": None,
            "evolution": {
                "state": "empty",
                "message": "No architecture memory snapshots recorded yet."
            },
        }
