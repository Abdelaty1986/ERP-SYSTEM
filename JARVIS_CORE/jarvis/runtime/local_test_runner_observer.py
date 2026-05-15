import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ROOT.parent
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "local_test_runner_observer.json"
LOG_PATH = LOGS_DIR / "local_test_runner_observer.jsonl"

TEST_CONFIGS = [
    "pytest.ini",
    "tox.ini",
    "noxfile.py",
    "pyproject.toml",
    "setup.cfg",
    "package.json",
    "jest.config.js",
    "vitest.config.js",
]


class LocalTestRunnerObserver:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        configs = []
        for relative in TEST_CONFIGS:
            path = PROJECT_ROOT / relative
            configs.append({
                "relative_path": relative,
                "exists": path.exists(),
                "kind": "file" if path.is_file() else "directory" if path.is_dir() else "missing",
            })

        test_dirs = []
        for relative in ["tests", "JARVIS_CORE/tests"]:
            path = PROJECT_ROOT / relative
            test_dirs.append({
                "relative_path": relative,
                "exists": path.exists(),
                "kind": "directory" if path.is_dir() else "file" if path.is_file() else "missing",
            })

        python_test_files = self.find_python_tests()
        likely_runners = []
        if any(item["relative_path"] in {"pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg"} and item["exists"] for item in configs):
            likely_runners.append("pytest_or_python_test_tooling")
        if any(item["relative_path"] == "package.json" and item["exists"] for item in configs):
            likely_runners.append("npm_script_test_tooling")
        if python_test_files:
            likely_runners.append("python_test_files_present")

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "local_test_runner_observer",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "awareness_mode": "safe_read_only_test_runner_observation",
            "phase": "phase_5_external_toolchain_runtime",
            "layer": "local_test_runner_observer",
            "project_root": str(PROJECT_ROOT),
            "test_configs": configs,
            "test_directories": test_dirs,
            "python_test_file_count": len(python_test_files),
            "sample_python_test_files": python_test_files[:20],
            "likely_test_runners": sorted(set(likely_runners)),
            "test_runner_state": "detected" if likely_runners else "not_detected",
            "risk_signal": "low",
            "prohibited_actions": [
                "heavy_test_execution_without_request",
                "test_database_mutation",
                "coverage_artifact_cleanup",
                "destructive_fixture_reset",
            ],
            "notes": [
                "Test runner observer did not execute tests.",
                "Detected files and configs are reported for planning only.",
            ],
            "recommendation": "use_as_input_for_dependency_health_observer",
            "result": "local_test_runner_observer_built",
        }

        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def find_python_tests(self):
        results = []
        ignored_parts = {".git", "__pycache__", ".venv", "venv", "node_modules"}
        for path in PROJECT_ROOT.rglob("*.py"):
            if any(part in ignored_parts for part in path.parts):
                continue
            name = path.name.lower()
            if name.startswith("test_") or name.endswith("_test.py") or "test" in path.parts:
                results.append(str(path.relative_to(PROJECT_ROOT)))
        return sorted(results)

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "test_runner_state": result["test_runner_state"],
            "python_test_file_count": result["python_test_file_count"],
            "likely_test_runners": result["likely_test_runners"],
            "execution_allowed": False,
            "apply_allowed": False,
            "human_approval_required": True,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(LocalTestRunnerObserver().build(), ensure_ascii=False, indent=2))
