from datetime import datetime
from pathlib import Path
import shutil
import os


class RuntimeHealthMonitor:
    def __init__(self, base_path="."):
        self.base_path = Path(base_path)

    def disk_status(self):
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

    def runtime_logs_status(self):
        logs_dir = self.base_path / "JARVIS_CORE/runtime_logs"

        if not logs_dir.exists():
            return {
                "exists": False,
                "files": 0,
            }

        files = list(logs_dir.glob("**/*"))

        return {
            "exists": True,
            "files": len(files),
        }

    def memory_status(self):
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")

            total_ram = round((pages * page_size) / (1024**3), 2)

            return {
                "available": True,
                "total_ram_gb": total_ram,
            }

        except Exception:
            return {
                "available": False,
                "total_ram_gb": None,
            }

    def overall_health(self):
        disk = self.disk_status()

        status = "healthy"

        if disk["usage_percent"] >= 90:
            status = "critical"
        elif disk["usage_percent"] >= 75:
            status = "warning"

        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "status": status,
            "disk": disk,
            "memory": self.memory_status(),
            "runtime_logs": self.runtime_logs_status(),
        }
