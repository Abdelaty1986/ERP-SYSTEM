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


def build_prompt(task_text):
    return f"""
You are LedgerX ERP AI Developer.

IMPORTANT RULES:
- NEVER modify database.db
- NEVER modify migrations.py
- NEVER touch accounting posting logic
- NEVER touch security/authentication
- ONLY suggest safe changes
- Target branch is dev-ai only
- Output JSON only

TASK:

{task_text}

Return JSON in this format:

{{
  "summary": "...",
  "risk_level": "LOW",
  "target_files": [],
  "suggested_changes": [],
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
        "raw_response": content,
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
