from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


class RuntimeHealthMonitor:
    def __init__(self, base_path="."):
        self.base_path = Path(base_path)
        self.logs_dir = self.base_path / "JARVIS_CORE/runtime_logs"
        self.queue_file = self.logs_dir / "runtime_command_queue.jsonl"
        self.timeline_file = self.logs_dir / "runtime_timeline.jsonl"
        self.worker_state_file = self.logs_dir / "runtime_worker_state.json"

    def utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    def disk_status(self) -> Dict[str, Any]:
        usage = shutil.disk_usage(self.base_path)

        total_gb = round(usage.total / (1024**3), 2)
        used_gb = round(usage.used / (1024**3), 2)
        free_gb = round(usage.free / (1024**3), 2)
        usage_percent = round((usage.used / usage.total) * 100, 2)

        return {
            "total_gb": total_gb,
            "used_gb": used_gb,
            "free_gb": free_gb,
            "usage_percent": usage_percent,
        }

    def runtime_logs_status(self) -> Dict[str, Any]:
        if not self.logs_dir.exists():
            return {"exists": False, "files": 0}

        files = [p for p in self.logs_dir.glob("**/*") if p.is_file()]
        return {"exists": True, "files": len(files)}

    def memory_status(self) -> Dict[str, Any]:
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            total_ram = round((pages * page_size) / (1024**3), 2)
            return {"available": True, "total_ram_gb": total_ram}
        except Exception:
            return {"available": False, "total_ram_gb": None}

    def queue_status(self) -> Dict[str, Any]:
        if not self.queue_file.exists():
            return {"exists": False, "items": 0, "queued": 0, "warnings": ["queue_file_missing"]}

        items: List[Dict[str, Any]] = []
        bad_lines = 0

        for line in self.queue_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                bad_lines += 1

        queued = len([i for i in items if i.get("status") == "queued"])
        warnings = []

        if bad_lines:
            warnings.append("queue_has_bad_lines")
        if queued >= 10:
            warnings.append("queue_backlog_high")

        return {
            "exists": True,
            "items": len(items),
            "queued": queued,
            "bad_lines": bad_lines,
            "warnings": warnings,
        }

    def timeline_status(self) -> Dict[str, Any]:
        if not self.timeline_file.exists():
            return {"exists": False, "events": 0, "warnings": ["timeline_missing"]}

        lines = [line for line in self.timeline_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        return {"exists": True, "events": len(lines), "warnings": []}

    def worker_status(self) -> Dict[str, Any]:
        if not self.worker_state_file.exists():
            return {
                "exists": False,
                "worker_status": "unknown",
                "warnings": ["worker_state_missing"],
            }

        try:
            state = json.loads(self.worker_state_file.read_text(encoding="utf-8"))
        except Exception:
            return {
                "exists": True,
                "worker_status": "corrupted",
                "warnings": ["worker_state_corrupted"],
            }

        warnings = []
        if state.get("worker_status") == "corrupted":
            warnings.append("worker_state_corrupted")

        return {
            "exists": True,
            "worker_status": state.get("worker_status", "unknown"),
            "last_heartbeat": state.get("last_heartbeat"),
            "last_command": state.get("last_command"),
            "last_result": state.get("last_result"),
            "warnings": warnings,
        }

    def overall_health(self) -> Dict[str, Any]:
        disk = self.disk_status()
        queue = self.queue_status()
        timeline = self.timeline_status()
        worker = self.worker_status()

        warnings = []
        warnings.extend(queue.get("warnings", []))
        warnings.extend(timeline.get("warnings", []))
        warnings.extend(worker.get("warnings", []))

        status = "healthy"

        if disk["usage_percent"] >= 90 or "worker_state_corrupted" in warnings or "queue_has_bad_lines" in warnings:
            status = "critical"
        elif disk["usage_percent"] >= 75 or warnings:
            status = "warning"

        return {
            "timestamp": self.utc_now(),
            "status": status,
            "warnings": warnings,
            "disk": disk,
            "memory": self.memory_status(),
            "runtime_logs": self.runtime_logs_status(),
            "queue": queue,
            "timeline": timeline,
            "worker": worker,
            "repair_mode": "simulation_only",
        }
