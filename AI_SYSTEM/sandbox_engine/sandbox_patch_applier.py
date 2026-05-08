from pathlib import Path
from datetime import datetime
import json
import shutil
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SANDBOX_ROOT = PROJECT_ROOT / "AI_SANDBOX"
PATCH_DIR = PROJECT_ROOT / "AI_TASKS" / "generated_patches"
RESULTS_DIR = PROJECT_ROOT / "AI_TASKS" / "sandbox_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    "AI_SANDBOX",
}

def ignore_patterns(dir_path, names):
    ignored = []
    for name in names:
        if name in EXCLUDE_DIRS:
            ignored.append(name)
        if name.endswith(".pyc"):
            ignored.append(name)
    return ignored

def latest_patch():
    files = sorted(PATCH_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None, None
    p = files[0]
    return p, json.loads(p.read_text(encoding="utf-8"))

def apply_patch_operation(operation):
    if operation.get("type") != "replace_text":
        return False, f"Unsupported operation type: {operation.get('type')}"

    rel_file = operation.get("file")
    old_text = operation.get("old_text", "")
    new_text = operation.get("new_text", "")

    target = SANDBOX_ROOT / rel_file

    if not target.exists():
        return False, f"Target file not found in sandbox: {rel_file}"

    content = target.read_text(encoding="utf-8")

    if old_text not in content:
        if new_text and new_text in content:
            return True, f"Already applied in target file: {rel_file}"
        return False, f"old_text not found in target file: {rel_file}"

    content = content.replace(old_text, new_text, 1)
    target.write_text(content, encoding="utf-8")

    return True, f"Applied replace_text to {rel_file}"

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
    patch_file, patch = latest_patch()

    if not patch:
        print("No generated patch found.")
        return 1

    if SANDBOX_ROOT.exists():
        shutil.rmtree(SANDBOX_ROOT)

    shutil.copytree(PROJECT_ROOT, SANDBOX_ROOT, ignore=ignore_patterns)

    applied = []
    failed = []

    for operation in patch.get("operations", []):
        ok, message = apply_patch_operation(operation)
        item = {"operation": operation, "ok": ok, "message": message}
        if ok:
            applied.append(item)
        else:
            failed.append(item)

    checks = []
    if not failed:
        checks.append(run_command("python -m py_compile app.py", SANDBOX_ROOT))
        checks.append(run_command("python AI_SYSTEM/pipelines/AI_DEV_PIPELINE.py", SANDBOX_ROOT))

    status = "PASSED" if not failed and all(c["ok"] for c in checks) else "FAILED"

    report = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "SANDBOX_PATCH_APPLY_ONLY",
        "patch_file": str(patch_file),
        "sandbox_path": str(SANDBOX_ROOT),
        "status": status,
        "applied": applied,
        "failed": failed,
        "checks": checks,
        "rules": [
            "Patch was applied inside sandbox only.",
            "Production files were not modified.",
            "Exact old_text match was required.",
            "Validation must pass before human-approved production apply.",
        ],
    }

    out = RESULTS_DIR / f"sandbox_patch_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Sandbox patch result generated:")
    print(out)
    print("Status:", status)

    return 0 if status == "PASSED" else 1

if __name__ == "__main__":
    sys.exit(main())
