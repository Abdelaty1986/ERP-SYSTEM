import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ROOT.parent
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "ci_cd_awareness_runtime.json"
LOG_PATH = LOGS_DIR / "ci_cd_awareness_runtime.jsonl"

CI_CD_PATHS = [
    ".github/workflows",
    ".gitlab-ci.yml",
    "azure-pipelines.yml",
    "Jenkinsfile",
    ".circleci/config.yml",
    ".buildkite/pipeline.yml",
    "Procfile",
    "nixpacks.toml",
    "render.yaml",
    "vercel.json",
    "netlify.toml",
    "deploy.sh",
]


class CiCdAwarenessRuntime:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        observed = []
        for relative in CI_CD_PATHS:
            path = PROJECT_ROOT / relative
            entry = {
                "relative_path": relative,
                "path": str(path),
                "exists": path.exists(),
                "kind": "directory" if path.is_dir() else "file" if path.is_file() else "missing",
            }
            if path.is_dir() and relative == ".github/workflows":
                entry["workflow_files"] = sorted(child.name for child in path.iterdir() if child.is_file())
            observed.append(entry)

        detected = [item for item in observed if item["exists"]]
        workflow_count = 0
        for item in detected:
            workflow_count += len(item.get("workflow_files", []))

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "ci_cd_awareness_runtime",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "awareness_mode": "safe_read_only_ci_cd_observation",
            "phase": "phase_5_external_toolchain_runtime",
            "layer": "ci_cd_awareness_runtime",
            "project_root": str(PROJECT_ROOT),
            "observed_paths": observed,
            "detected_paths": [item["relative_path"] for item in detected],
            "detected_path_count": len(detected),
            "workflow_file_count": workflow_count,
            "ci_cd_awareness_state": "detected" if detected else "not_detected",
            "risk_signal": "watch" if detected else "low",
            "prohibited_actions": [
                "deploy",
                "remote_ci_trigger",
                "workflow_dispatch",
                "git_push",
                "secret_mutation",
            ],
            "notes": [
                "CI/CD awareness is observation-only.",
                "No remote operations, deployments, or workflow triggers were executed.",
                "Configuration files were detected by path only.",
            ],
            "recommendation": "use_as_input_for_local_test_runner_observer",
            "result": "ci_cd_awareness_runtime_built",
        }

        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "ci_cd_awareness_state": result["ci_cd_awareness_state"],
            "detected_path_count": result["detected_path_count"],
            "workflow_file_count": result["workflow_file_count"],
            "execution_allowed": False,
            "apply_allowed": False,
            "human_approval_required": True,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(CiCdAwarenessRuntime().build(), ensure_ascii=False, indent=2))
