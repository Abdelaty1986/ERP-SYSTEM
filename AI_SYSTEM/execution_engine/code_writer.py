import json
import os
from datetime import datetime
from pathlib import Path

import google.generativeai as genai


ROOT = Path(__file__).resolve().parents[2]
APPROVED_DIR = ROOT / "AI_TASKS" / "approved"
CODE_REPORTS_DIR = ROOT / "AI_TASKS" / "code_writer_reports"

MODEL_NAME = "gemini-2.5-flash-lite"
MAX_RAW_RESPONSE_CHARS = int(os.environ.get("LEDGERX_CODE_WRITER_MAX_RAW_CHARS", "240000"))
MAX_DIFF_ITEMS_PER_FILE = int(os.environ.get("LEDGERX_CODE_WRITER_MAX_DIFF_ITEMS", "80"))
MAX_TARGET_FILES = int(os.environ.get("LEDGERX_CODE_WRITER_MAX_TARGET_FILES", "12"))


class CodeWriterInvalidJSON(RuntimeError):
    pass


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def read_task(task_id):
    path = APPROVED_DIR / f"{task_id}.md"
    if not path.exists():
        raise FileNotFoundError(f"Task not found: {path}")
    return path.read_text(encoding="utf-8")


def read_project_context():
    context_files = [
        "templates/dashboard.html",
        "templates/layout.html",
        "static/css/dashboard.css",
        "static/css/ledgerx_enterprise_theme.css",
        "static/css/style.css",
    ]

    parts = []

    for file_path in context_files:
        path = ROOT / file_path
        if path.exists():
            content = path.read_text(encoding="utf-8", errors="ignore")
            parts.append(f"FILE: {file_path}\n---START---\n{content[:6000]}\n---END---")

    return "\n\n".join(parts)


def build_prompt(task_text):
    project_context = read_project_context()

    return f"""
You are LedgerX ERP AI Developer working on a Python Flask ERP project.

REAL PROJECT STRUCTURE:
- Flask app entry: app.py
- HTML templates live under: templates/
- CSS files live under: static/css/
- JavaScript files live under: static/js/
- Python modules live under: modules/
- AI system files live under: AI_SYSTEM/
- This is NOT a React project.
- This is NOT a Next.js project.
- NEVER suggest src/app/... files.
- NEVER suggest .tsx or .jsx files.

IMPORTANT RULES:
- NEVER modify database.db
- NEVER modify migrations.py unless explicitly requested
- NEVER touch accounting posting logic
- NEVER touch security/authentication
- ONLY suggest safe changes
- Target branch is dev-ai only
- For dashboard UI, prefer templates/dashboard.html and static/css/*.css
- Output valid raw JSON only. Do not wrap it in markdown. Do not use ```json. Do not add explanations outside JSON.
- target_files must be real plausible Flask project files only
- suggested_changes.diff must always be a list of objects with original_line and new_line
- original_line must be copied exactly from REAL FILE CONTENT CONTEXT
- Never return unified diff text
- Never return patch text starting with --- or +++
- Never return no-op changes. original_line and new_line must not be identical.
- Keep output compact. Prefer fewer high-quality changes over huge repeated JSON.

REAL FILE CONTENT CONTEXT:\n\n{project_context}\n\nTASK:\n\n{task_text}\n\nReturn JSON in this format:

{{
  "summary": "...",
  "risk_level": "LOW",
  "target_files": [],
  "suggested_changes": [{{"file": "templates/example.html", "diff": [{{"original_line": "exact existing line", "new_line": "replacement line"}}]}}],
  "safe_to_apply": true
}}
"""


def generate_plan(task_text):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY")

    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(MODEL_NAME)

    response = model.generate_content(build_prompt(task_text))

    return response.text or ""


def strip_markdown_fences(text):
    cleaned = (text or "").strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:].strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()
    return cleaned


def extract_json_object(text):
    cleaned = strip_markdown_fences(text)
    if not cleaned:
        raise CodeWriterInvalidJSON("Empty model response")

    try:
        return cleaned, json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    if start < 0:
        raise CodeWriterInvalidJSON("No JSON object start found in model response")

    in_string = False
    escaped = False
    depth = 0

    for index in range(start, len(cleaned)):
        char = cleaned[index]

        if escaped:
            escaped = False
            continue

        if char == "\\" and in_string:
            escaped = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = cleaned[start:index + 1]
                try:
                    return candidate, json.loads(candidate)
                except json.JSONDecodeError as exc:
                    raise CodeWriterInvalidJSON(f"Extracted JSON is invalid: {exc}") from exc

    raise CodeWriterInvalidJSON("No complete JSON object found in model response")


def normalize_plan(plan):
    if not isinstance(plan, dict):
        raise CodeWriterInvalidJSON("Plan root must be a JSON object")

    normalized = {
        "summary": str(plan.get("summary", "")).strip()[:2000],
        "risk_level": str(plan.get("risk_level", "LOW")).strip().upper() or "LOW",
        "target_files": [],
        "suggested_changes": [],
        "safe_to_apply": bool(plan.get("safe_to_apply", False)),
    }

    target_files = plan.get("target_files", [])
    if isinstance(target_files, list):
        normalized["target_files"] = [str(item).strip() for item in target_files if str(item).strip()][:MAX_TARGET_FILES]

    suggested_changes = plan.get("suggested_changes", [])
    if not isinstance(suggested_changes, list):
        raise CodeWriterInvalidJSON("suggested_changes must be a list")

    for change in suggested_changes[:MAX_TARGET_FILES]:
        if not isinstance(change, dict):
            continue

        file_path = str(change.get("file", "")).strip()
        diff_items = change.get("diff", [])
        if not file_path or not isinstance(diff_items, list):
            continue

        clean_diff = []
        seen_pairs = set()

        for item in diff_items[:MAX_DIFF_ITEMS_PER_FILE]:
            if not isinstance(item, dict):
                continue

            original = str(item.get("original_line", ""))
            replacement = str(item.get("new_line", ""))

            if not original or not replacement:
                continue

            if original == replacement:
                continue

            pair = (original, replacement)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            clean_diff.append({
                "original_line": original,
                "new_line": replacement,
            })

        if clean_diff:
            normalized["suggested_changes"].append({
                "file": file_path,
                "diff": clean_diff,
            })

    if normalized["safe_to_apply"] and not normalized["suggested_changes"]:
        normalized["safe_to_apply"] = False
        normalized["summary"] = (normalized["summary"] + " | No valid non-no-op changes were produced.").strip()

    return normalized


def save_raw_failure(task_id, raw_content, reason):
    CODE_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    raw_path = CODE_REPORTS_DIR / f"{task_id}_raw_response.txt"
    raw_path.write_text(raw_content or "", encoding="utf-8")

    report_path = CODE_REPORTS_DIR / f"{task_id}_code_writer.json"
    payload = {
        "timestamp": now(),
        "task_id": task_id,
        "model": MODEL_NAME,
        "status": "FAILED_CODE_WRITER_INVALID_JSON",
        "safe_to_apply": False,
        "error": str(reason),
        "raw_response_path": str(raw_path),
        "raw_response_preview": (raw_content or "")[:3000],
        "raw_response": "{}",
    }

    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def save_report(task_id, content):
    CODE_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    report_path = CODE_REPORTS_DIR / f"{task_id}_code_writer.json"

    if len(content or "") > MAX_RAW_RESPONSE_CHARS:
        return save_raw_failure(
            task_id,
            content,
            f"Model response exceeded max size: {len(content)} > {MAX_RAW_RESPONSE_CHARS}",
        )

    try:
        extracted_json, parsed_plan = extract_json_object(content)
        normalized_plan = normalize_plan(parsed_plan)
    except Exception as exc:
        return save_raw_failure(task_id, content, exc)

    payload = {
        "timestamp": now(),
        "task_id": task_id,
        "model": MODEL_NAME,
        "status": "READY_FOR_PATCH" if normalized_plan.get("safe_to_apply") else "NO_VALID_CHANGES",
        "raw_response": json.dumps(normalized_plan, ensure_ascii=False),
        "normalized_plan": normalized_plan,
        "extracted_json_preview": extracted_json[:3000],
    }

    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return report_path


def main():
    task_id = os.environ.get("LEDGERX_APPROVED_TASK_ID", "").strip()

    if not task_id:
        raise RuntimeError("Missing LEDGERX_APPROVED_TASK_ID")

    task_text = read_task(task_id)

    result = generate_plan(task_text)

    report = save_report(task_id, result)

    print("Code writer completed")
    print(report)
    print(result[:5000])


if __name__ == "__main__":
    main()
