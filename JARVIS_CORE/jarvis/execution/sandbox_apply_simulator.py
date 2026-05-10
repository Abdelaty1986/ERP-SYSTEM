from pathlib import Path
from datetime import datetime
import hashlib
import shutil


class SandboxApplySimulator:
    """
    Simulates applying materialized patch artifacts to sandbox copies only.
    It never modifies original project files.
    """

    def __init__(self, root="."):
        self.root = Path(root)
        self.simulation_dir = (
            self.root
            / "JARVIS_CORE/jarvis/execution/sandbox/apply_simulations"
        )
        self.simulation_dir.mkdir(parents=True, exist_ok=True)

    def _timestamp(self):
        return datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    def _hash_file(self, file_path):
        path = Path(file_path)

        if not path.exists() or not path.is_file():
            return None

        sha = hashlib.sha256()

        with open(path, "rb") as f:
            while chunk := f.read(8192):
                sha.update(chunk)

        return sha.hexdigest()

    def simulate(self, staged_files, materialized_patches):
        timestamp = self._timestamp()
        run_dir = self.simulation_dir / timestamp
        run_dir.mkdir(parents=True, exist_ok=True)

        copied_files = []

        for item in staged_files or []:
            source = Path(item.get("staged", ""))

            if not source.exists() or not source.is_file():
                continue

            destination = run_dir / source.name
            shutil.copy2(source, destination)

            copied_files.append({
                "source": str(source),
                "simulation_copy": str(destination),
                "hash": self._hash_file(destination),
            })

        result = {
            "status": "simulated",
            "timestamp": timestamp,
            "simulation_dir": str(run_dir),
            "copied_files": copied_files,
            "patch_artifacts": materialized_patches or [],
            "original_files_modified": False,
        }

        return result
