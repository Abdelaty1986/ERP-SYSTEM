import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ROOT.parent
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "dependency_health_observer.json"
LOG_PATH = LOGS_DIR / "dependency_health_observer.jsonl"

DEPENDENCY_FILES = [
    "requirements.txt",
    "pyproject.toml",
    "Pipfile",
    "poetry.lock",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "environment.yml",
]


class DependencyHealthObserver:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        files = []
        dependency_counts = {}
        lock_files = []
        for relative in DEPENDENCY_FILES:
            path = PROJECT_ROOT / relative
            entry = {
                "relative_path": relative,
                "exists": path.exists(),
                "kind": "file" if path.is_file() else "directory" if path.is_dir() else "missing",
                "read_mode": "metadata_only",
            }
            if path.is_file():
                entry["size_bytes"] = path.stat().st_size
                if relative == "requirements.txt":
                    count = self.count_requirements(path)
                    dependency_counts[relative] = count
                    entry["dependency_line_count"] = count
                if relative.endswith(".lock") or "lock" in relative:
                    lock_files.append(relative)
            files.append(entry)

        detected = [item for item in files if item["exists"]]
        primary_manifests = [
            item["relative_path"]
            for item in detected
            if item["relative_path"] in {"requirements.txt", "pyproject.toml", "package.json", "Pipfile", "environment.yml"}
        ]

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "dependency_health_observer",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "awareness_mode": "safe_read_only_dependency_observation",
            "phase": "phase_5_external_toolchain_runtime",
            "layer": "dependency_health_observer",
            "project_root": str(PROJECT_ROOT),
            "dependency_files": files,
            "detected_files": [item["relative_path"] for item in detected],
            "detected_file_count": len(detected),
            "primary_manifests": primary_manifests,
            "dependency_counts": dependency_counts,
            "lock_files_present": lock_files,
            "dependency_health_state": "detected" if detected else "not_detected",
            "risk_signal": "watch" if detected and not lock_files else "low",
            "prohibited_actions": [
                "package_install",
                "package_upgrade",
                "lockfile_write",
                "dependency_resolution",
                "network_package_fetch",
            ],
            "notes": [
                "Dependency observer inspected files only.",
                "No packages were installed, upgraded, resolved, or downloaded.",
                "No dependency or lock files were modified.",
            ],
            "recommendation": "use_as_input_for_toolchain_risk_classifier",
            "result": "dependency_health_observer_built",
        }

        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def count_requirements(self, path):
        count = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                count += 1
        return count

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "dependency_health_state": result["dependency_health_state"],
            "detected_file_count": result["detected_file_count"],
            "primary_manifests": result["primary_manifests"],
            "execution_allowed": False,
            "apply_allowed": False,
            "human_approval_required": True,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(DependencyHealthObserver().build(), ensure_ascii=False, indent=2))
