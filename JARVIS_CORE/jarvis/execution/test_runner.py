from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any
import subprocess
import sys


@dataclass
class TestCommand:
    name: str
    command: List[str]
    reason: str


class TestRunner:
    """
    Detects and runs safe project tests.
    It does NOT modify files.
    """

    def __init__(self, project_root: str = ".", timeout_seconds: int = 45):
        self.project_root = Path(project_root)
        self.timeout_seconds = timeout_seconds

    def discover_tests(self) -> Dict[str, Any]:
        commands: List[TestCommand] = []

        tests_dir = self.project_root / "tests"

        if tests_dir.exists():
            commands.append(TestCommand(
                name="python_compile_tests",
                command=[sys.executable, "-m", "compileall", "tests"],
                reason="Compile Python files under tests directory."
            ))

        app_file = self.project_root / "app.py"
        if app_file.exists():
            commands.append(TestCommand(
                name="python_compile_app",
                command=[sys.executable, "-m", "py_compile", "app.py"],
                reason="Compile main Flask entry file."
            ))

        jarvis_dir = self.project_root / "JARVIS_CORE"
        if jarvis_dir.exists():
            commands.append(TestCommand(
                name="python_compile_jarvis_core",
                command=[sys.executable, "-m", "compileall", "JARVIS_CORE/jarvis"],
                reason="Compile Jarvis core Python package."
            ))

        return {
            "status": "discovered" if commands else "no_tests_found",
            "commands": [asdict(cmd) for cmd in commands],
        }

    def run_safe_tests(self, commands: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
        if commands is None:
            commands = self.discover_tests().get("commands", [])

        results = []

        for item in commands:
            command = item.get("command", [])
            name = item.get("name", "unknown_test")

            try:
                completed = subprocess.run(
                    command,
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                )

                results.append({
                    "name": name,
                    "command": command,
                    "returncode": completed.returncode,
                    "ok": completed.returncode == 0,
                    "stdout": completed.stdout[-3000:],
                    "stderr": completed.stderr[-3000:],
                })

            except subprocess.TimeoutExpired:
                results.append({
                    "name": name,
                    "command": command,
                    "returncode": None,
                    "ok": False,
                    "stdout": "",
                    "stderr": f"Test timed out after {self.timeout_seconds} seconds.",
                })

            except Exception as exc:
                results.append({
                    "name": name,
                    "command": command,
                    "returncode": None,
                    "ok": False,
                    "stdout": "",
                    "stderr": str(exc),
                })

        overall = "passed" if results and all(r["ok"] for r in results) else "failed"
        if not results:
            overall = "no_tests_run"

        return {
            "status": overall,
            "results": results,
            "summary": self._summary(results),
        }

    def _summary(self, results: List[Dict[str, Any]]) -> str:
        if not results:
            return "No tests were run."

        passed = sum(1 for result in results if result.get("ok"))
        failed = len(results) - passed

        return f"{passed} test command(s) passed, {failed} failed."
