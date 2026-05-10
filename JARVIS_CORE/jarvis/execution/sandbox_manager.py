from pathlib import Path
from datetime import datetime
import hashlib
import shutil


class SandboxManager:
    def __init__(self, root="."):
        self.root = Path(root)

        self.sandbox_dir = (
            self.root / "JARVIS_CORE/jarvis/execution/sandbox"
        )

        self.backup_dir = (
            self.root / "JARVIS_CORE/jarvis/execution/backups"
        )

        self.staging_dir = (
            self.root / "JARVIS_CORE/jarvis/execution/staging"
        )

        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.staging_dir.mkdir(parents=True, exist_ok=True)

    def create_timestamp(self):
        return datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    def calculate_hash(self, file_path):
        path = Path(file_path)

        if not path.exists():
            return None

        sha = hashlib.sha256()

        with open(path, "rb") as f:
            while chunk := f.read(8192):
                sha.update(chunk)

        return sha.hexdigest()

    def create_backup(self, file_path):
        source = Path(file_path)

        if not source.exists():
            return None

        timestamp = self.create_timestamp()

        backup_name = f"{source.name}.{timestamp}.bak"

        destination = self.backup_dir / backup_name

        shutil.copy2(source, destination)

        return {
            "source": str(source),
            "backup": str(destination),
            "timestamp": timestamp,
            "hash": self.calculate_hash(source),
        }

    def stage_file(self, file_path):
        source = Path(file_path)

        if not source.exists():
            return {
                "status": "missing",
                "source": str(source),
            }

        if source.is_dir():
            return {
                "status": "skipped_directory",
                "source": str(source),
            }

        destination = self.staging_dir / source.name

        shutil.copy2(source, destination)

        return {
            "status": "staged",
            "source": str(source),
            "staged": str(destination),
            "hash": self.calculate_hash(source),
        }
