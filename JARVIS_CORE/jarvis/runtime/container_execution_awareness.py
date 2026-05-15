import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ROOT.parent
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "container_execution_awareness.json"
LOG_PATH = LOGS_DIR / "container_execution_awareness.jsonl"

CONTAINER_FILES = [
    "Dockerfile",
    "Containerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    ".dockerignore",
    ".devcontainer/devcontainer.json",
    ".devcontainer/Dockerfile",
]


class ContainerExecutionAwareness:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        observed_files = []
        for relative in CONTAINER_FILES:
            path = PROJECT_ROOT / relative
            observed_files.append({
                "relative_path": relative,
                "path": str(path),
                "exists": path.exists(),
                "kind": "directory" if path.is_dir() else "file" if path.is_file() else "missing",
            })

        detected_files = [item for item in observed_files if item["exists"]]
        compose_present = any("compose" in item["relative_path"] for item in detected_files)
        image_definition_present = any(
            item["relative_path"] in {"Dockerfile", "Containerfile", ".devcontainer/Dockerfile"}
            for item in detected_files
        )

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "container_execution_awareness",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "awareness_mode": "safe_read_only_container_observation",
            "phase": "phase_5_external_toolchain_runtime",
            "layer": "container_execution_awareness",
            "project_root": str(PROJECT_ROOT),
            "observed_files": observed_files,
            "detected_file_count": len(detected_files),
            "detected_files": [item["relative_path"] for item in detected_files],
            "container_signals": {
                "compose_present": compose_present,
                "image_definition_present": image_definition_present,
                "devcontainer_present": any(item["relative_path"].startswith(".devcontainer") for item in detected_files),
            },
            "container_awareness_state": "detected" if detected_files else "not_detected",
            "risk_signal": "watch" if detected_files else "low",
            "prohibited_actions": [
                "docker_build",
                "docker_run",
                "docker_compose_up",
                "podman_run",
                "container_mutation",
            ],
            "notes": [
                "Container awareness is observation-only.",
                "No Docker, Podman, or compose commands were executed.",
                "No images, networks, volumes, or containers were created or modified.",
            ],
            "recommendation": "use_as_input_for_ci_cd_awareness_runtime",
            "result": "container_execution_awareness_built",
        }

        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "container_awareness_state": result["container_awareness_state"],
            "detected_file_count": result["detected_file_count"],
            "execution_allowed": False,
            "apply_allowed": False,
            "human_approval_required": True,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(ContainerExecutionAwareness().build(), ensure_ascii=False, indent=2))
