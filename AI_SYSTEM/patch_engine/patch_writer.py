from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PATCH_FILES_DIR = PROJECT_ROOT / "AI_TASKS" / "patch_files"
PATCH_FILES_DIR.mkdir(parents=True, exist_ok=True)

def write_review_patch(title, content):
    safe_title = title.replace(" ", "_").lower()
    out = PATCH_FILES_DIR / f"{safe_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.patch.txt"

    body = f"""# LedgerX AI Patch Draft
# Mode: REVIEW_ONLY
# This file is a draft for human review.
# It must not be auto-applied.

{content}
"""
    out.write_text(body, encoding="utf-8")
    return out

def main():
    out = write_review_patch(
        "sample_patch",
        "No code changes generated yet. Patch Engine initialized successfully."
    )
    print("Review patch draft generated:")
    print(out)

if __name__ == "__main__":
    main()
