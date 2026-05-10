import subprocess
import sys
from pathlib import Path


class SandboxPostApplyTester:
    """
    Runs safe compile checks on sandbox files after sandbox apply.
    It does not touch original project files.
    """

    def run(self, sandbox_patch_apply):
        results = []

        for item in sandbox_patch_apply.get("applied", []):
            sandbox_file = item.get("sandbox_file")

            if not sandbox_file:
                continue

            path = Path(sandbox_file)

            if not path.exists() or not path.is_file():
                results.append({
                    "file": sandbox_file,
                    "status": "missing",
                    "ok": False,
                })
                continue

            if path.suffix == ".py":
                command = [
                    sys.executable,
                    "-m",
                    "py_compile",
                    str(path),
                ]

                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                )

                results.append({
                    "file": str(path),
                    "status": "passed" if completed.returncode == 0 else "failed",
                    "ok": completed.returncode == 0,
                    "command": command,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                })
            else:
                results.append({
                    "file": str(path),
                    "status": "skipped_non_python",
                    "ok": True,
                })

        failed = [item for item in results if not item.get("ok")]

        return {
            "status": "passed" if not failed else "failed",
            "ok": not failed,
            "results": results,
            "failed_count": len(failed),
            "checked_count": len(results),
        }
