import json
import os
import subprocess
import base64
from urllib import request, parse
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT / "AI_TASKS" / "code_writer_reports"
APPLY_REPORTS_DIR = ROOT / "AI_TASKS" / "apply_reports"

BLOCKED_PARTS = [
    "database.db",
    "migrations.py",
    "modules/accounting/",
    "modules/sales/",
    "modules/inventory/",
    "auth",
    "login",
    "password",
    "posting",
    "ledger",
    "journal",
]


class SafePatchPlanError(RuntimeError):
    pass


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def latest_code_writer_report(task_id):
    path = REPORTS_DIR / f"{task_id}_code_writer.json"
    if not path.exists():
        raise FileNotFoundError(f"Code writer report not found: {path}")
    return path


def write_apply_report(task_id, status, source_report=None, applied=None, skipped=None, validation=None, git_result=None, error=None):
    APPLY_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    final = {
        "timestamp": now(),
        "task_id": task_id,
        "source_report": str(source_report) if source_report else None,
        "status": status,
        "applied": applied or [],
        "skipped": skipped or [],
        "validation": validation or {"skipped": True},
        "git": git_result or {"skipped": True},
    }

    if error:
        final["error"] = str(error)

    out = APPLY_REPORTS_DIR / f"{task_id}_apply_report.json"
    out.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Safe patch applier finished")
    print(out)
    print(json.dumps(final, ensure_ascii=False, indent=2))

    return final


def load_json_file(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SafePatchPlanError(f"Code writer report file is invalid JSON: {exc}") from exc


def load_plan(task_id):
    report_path = latest_code_writer_report(task_id)
    report = load_json_file(report_path)

    report_status = str(report.get("status", "")).strip()
    if report_status in {"FAILED_CODE_WRITER_INVALID_JSON", "NO_VALID_CHANGES"}:
        raise SafePatchPlanError(
            f"Code writer report is not ready for patching: {report_status}. "
            f"Details: {report.get('error') or report.get('raw_response_preview') or 'No details'}"
        )

    if isinstance(report.get("normalized_plan"), dict):
        return report["normalized_plan"], report_path

    raw = report.get("raw_response", "")
    if isinstance(raw, dict):
        return raw, report_path

    raw = str(raw or "").strip()
    if not raw:
        raise SafePatchPlanError("Code writer report has empty raw_response")

    try:
        plan = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SafePatchPlanError(f"Code writer raw_response is invalid JSON: {exc}") from exc

    if not isinstance(plan, dict):
        raise SafePatchPlanError("Code writer plan must be a JSON object")

    return plan, report_path


def is_safe_file(file_path):
    normalized = file_path.replace("\\", "/").lower()

    if normalized.startswith("/"):
        return False, "Absolute paths are not allowed."

    if ".." in normalized:
        return False, "Parent path traversal is not allowed."

    for blocked in BLOCKED_PARTS:
        if blocked in normalized:
            return False, f"Blocked protected area: {blocked}"

    allowed_prefixes = (
        "templates/",
        "static/css/",
        "static/js/",
        "AI_SYSTEM/",
    )

    if not normalized.startswith(allowed_prefixes):
        return False, "Only templates, static assets, and AI_SYSTEM files are allowed."

    return True, ""


def apply_line_replacements(plan):
    applied = []
    skipped = []

    if not isinstance(plan, dict):
        return applied, [{"reason": "Plan is not a JSON object"}]

    if not plan.get("safe_to_apply"):
        return applied, [{"reason": "Plan safe_to_apply is not true"}]

    changes = plan.get("suggested_changes", [])
    if not isinstance(changes, list):
        return applied, [{"reason": "suggested_changes must be a list"}]

    for change in changes:
        if not isinstance(change, dict):
            skipped.append({"reason": "Invalid change item type"})
            continue

        file_path = change.get("file", "")
        safe, reason = is_safe_file(file_path)

        if not safe:
            skipped.append({"file": file_path, "reason": reason})
            continue

        full_path = ROOT / file_path

        if not full_path.exists():
            skipped.append({"file": file_path, "reason": "File does not exist"})
            continue

        text = full_path.read_text(encoding="utf-8")
        new_text = text
        file_applied = []

        diff_items = change.get("diff", [])

        if isinstance(diff_items, str):
            skipped.append({
                "file": file_path,
                "reason": "Unified/string diff is not supported. Expected list of original_line/new_line objects.",
            })
            continue

        if not isinstance(diff_items, list):
            skipped.append({"file": file_path, "reason": "diff must be a list"})
            continue

        for item in diff_items:
            if not isinstance(item, dict):
                skipped.append({"file": file_path, "reason": "Invalid diff item type"})
                continue

            original = item.get("original_line", "")
            replacement = item.get("new_line", "")

            if not original or not replacement:
                skipped.append({"file": file_path, "reason": "Invalid diff item"})
                continue

            if original == replacement:
                skipped.append({
                    "file": file_path,
                    "reason": "No-op change rejected",
                    "original_line": original,
                })
                continue

            if original not in new_text:
                skipped.append({
                    "file": file_path,
                    "reason": "Original line not found",
                    "original_line": original,
                })
                continue

            new_text = new_text.replace(original, replacement, 1)
            file_applied.append({
                "original_line": original,
                "new_line": replacement,
            })

        if file_applied and new_text != text:
            full_path.write_text(new_text, encoding="utf-8")
            applied.append({"file": file_path, "changes": file_applied})
        elif file_applied:
            skipped.append({"file": file_path, "reason": "Changes produced no file difference"})

    return applied, skipped


def run_validation():
    result = subprocess.run(
        ["python", "AI_SYSTEM/validators/validation_runner.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=900,
    )
    return {
        "returncode": result.returncode,
        "stdout_tail": (result.stdout or "")[-5000:],
        "stderr_tail": (result.stderr or "")[-5000:],
    }


def github_api(method, url, token, payload=None):
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url, data=data, headers=headers, method=method)

    with request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def github_commit_applied_files(task_id, applied):
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "Abdelaty1986/ERP-SYSTEM").strip()
    branch = os.environ.get("GITHUB_BRANCH", "dev-ai").strip()

    if not token:
        return {
            "committed": False,
            "pushed": False,
            "reason": "Missing GITHUB_TOKEN. Patch applied locally only.",
        }

    commits = []

    for item in applied:
        file_path = item.get("file")
        if not file_path:
            continue

        full_path = ROOT / file_path
        if not full_path.exists():
            continue

        encoded_path = parse.quote(file_path)
        api_url = f"https://api.github.com/repos/{repo}/contents/{encoded_path}?ref={branch}"

        current = github_api("GET", api_url, token)
        sha = current.get("sha")

        content = full_path.read_text(encoding="utf-8")
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("ascii")

        payload = {
            "message": f"ai apply approved task {task_id}: {file_path}",
            "content": encoded_content,
            "sha": sha,
            "branch": branch,
        }

        updated = github_api(
            "PUT",
            f"https://api.github.com/repos/{repo}/contents/{encoded_path}",
            token,
            payload,
        )

        commits.append({
            "file": file_path,
            "commit_sha": updated.get("commit", {}).get("sha"),
        })

    return {
        "committed": bool(commits),
        "pushed": bool(commits),
        "method": "github_api",
        "branch": branch,
        "commits": commits,
    }


def git_commit_if_needed(task_id):
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return {
            "committed": False,
            "pushed": False,
            "reason": "git is not available in Railway runtime. Patch was applied locally only."
        }

    changed = status.stdout.strip()

    if not changed:
        return {"committed": False, "reason": "No git changes detected"}

    subprocess.run(["git", "add", "."], cwd=ROOT, check=True)

    commit = subprocess.run(
        ["git", "commit", "-m", f"ai apply approved task {task_id}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    if commit.returncode != 0:
        return {
            "committed": False,
            "reason": "git commit failed",
            "stdout": commit.stdout[-3000:],
            "stderr": commit.stderr[-3000:],
        }

    push = subprocess.run(
        ["git", "push", "origin", "dev-ai"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    return {
        "committed": commit.returncode == 0,
        "pushed": push.returncode == 0,
        "commit_stdout": commit.stdout[-3000:],
        "commit_stderr": commit.stderr[-3000:],
        "push_stdout": push.stdout[-3000:],
        "push_stderr": push.stderr[-3000:],
    }


def main():
    task_id = os.environ.get("LEDGERX_APPROVED_TASK_ID", "").strip()

    if not task_id:
        raise RuntimeError("Missing LEDGERX_APPROVED_TASK_ID")

    source_report = None

    try:
        plan, source_report = load_plan(task_id)
    except Exception as exc:
        write_apply_report(
            task_id=task_id,
            status="FAILED_INVALID_CODE_WRITER_REPORT",
            source_report=source_report,
            error=exc,
            skipped=[{"reason": "Patch applier stopped before changing files"}],
        )
        return False

    applied, skipped = apply_line_replacements(plan)

    if not applied:
        write_apply_report(
            task_id=task_id,
            status="NOT_APPLIED",
            source_report=source_report,
            applied=applied,
            skipped=skipped or [{"reason": "No applicable changes"}],
            validation={"skipped": True, "reason": "No changes applied"},
            git_result={"skipped": True, "reason": "No changes applied"},
        )
        return False

    validation = run_validation()

    git_result = {"skipped": True, "reason": "Validation failed or no changes applied"}

    if validation["returncode"] == 0:
        git_result = github_commit_applied_files(task_id, applied)

    final = write_apply_report(
        task_id=task_id,
        status="APPLIED" if validation["returncode"] == 0 else "NOT_APPLIED",
        source_report=source_report,
        applied=applied,
        skipped=skipped,
        validation=validation,
        git_result=git_result,
    )

    return final["status"] == "APPLIED"


if __name__ == "__main__":
    ok = main()
    raise SystemExit(0 if ok else 1)
