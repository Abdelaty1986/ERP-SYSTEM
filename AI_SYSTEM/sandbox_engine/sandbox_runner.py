from pathlib import Path
from datetime import datetime
import json
import shutil
import subprocess

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SANDBOX_ROOT = PROJECT_ROOT / "AI_SANDBOX"
RESULTS_DIR = PROJECT_ROOT / "AI_TASKS" / "sandbox_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    "AI_SANDBOX",
}

EXCLUDE_FILES = set()

def ignore_patterns(dir_path, names):
    ignored = []
    for name in names:
        if name in EXCLUDE_DIRS or name in EXCLUDE_FILES:
            ignored.append(name)
        if name.endswith(".pyc"):
            ignored.append(name)
    return ignored

def run_command(command, cwd):
    result = subprocess.run(
        command,
        cwd=cwd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=240,
    )
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout[-3000:],
        "stderr": result.stderr[-3000:],
        "ok": result.returncode == 0,
    }

def main():
    if SANDBOX_ROOT.exists():
        shutil.rmtree(SANDBOX_ROOT)

    shutil.copytree(PROJECT_ROOT, SANDBOX_ROOT, ignore=ignore_patterns)

    checks = []
    checks.append(run_command("python -m py_compile app.py", SANDBOX_ROOT))
    checks.append(run_command("python AI_SYSTEM/pipelines/AI_DEV_PIPELINE.py", SANDBOX_ROOT))

    ok = all(item["ok"] for item in checks)

    report = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "SANDBOX_ONLY",
        "sandbox_path": str(SANDBOX_ROOT),
        "status": "PASSED" if ok else "FAILED",
        "checks": checks,
        "rules": [
            "Sandbox runner must not modify production files.",
            "database.db is copied only inside sandbox validation copy.",
            "Only validation commands are executed.",
        ],
    }

    out = RESULTS_DIR / f"sandbox_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Sandbox result generated:")
    print(out)
    print("Status:", report["status"])

if __name__ == "__main__":
    main()
