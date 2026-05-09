import json
import os
from datetime import datetime
from pathlib import Path

import google.generativeai as genai


ROOT = Path(__file__).resolve().parents[2]
APPROVED_DIR = ROOT / "AI_TASKS" / "approved"
CODE_REPORTS_DIR = ROOT / "AI_TASKS" / "code_writer_reports"

MODEL_NAME = "gemini-2.5-flash-lite"


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
            parts.append(f"FILE: {file_path}\\n---START---\\n{content[:6000]}\\n---END---")

    return "\\n\\n".join(parts)


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

    response = model.generate_content(
        build_prompt(task_text)
    )

    return response.text


def save_report(task_id, content):
    CODE_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    out = CODE_REPORTS_DIR / f"{task_id}_code_writer.json"

    payload = {
        "timestamp": now(),
        "task_id": task_id,
        "model": MODEL_NAME,
        "raw_response": content.strip().replace("```json", "").replace("```", "").strip(),
    }

    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return out


def main():
    task_id = os.environ.get("LEDGERX_APPROVED_TASK_ID", "").strip()

    if not task_id:
        raise RuntimeError("Missing LEDGERX_APPROVED_TASK_ID")

    task_text = read_task(task_id)

    result = generate_plan(task_text)

    report = save_report(task_id, result)

    print("Code writer completed")
    print(report)
    print(result)


if __name__ == "__main__":
    main()
