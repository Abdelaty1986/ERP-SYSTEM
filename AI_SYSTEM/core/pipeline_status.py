from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent.parent

HISTORY_FILE = ROOT / "AI_SYSTEM" / "logs" / "pipeline_history.json"


def get_latest_pipeline_status():
    if not HISTORY_FILE.exists():
        return {
            "exists": False
        }

    data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))

    runs = data.get("runs", [])

    if not runs:
        return {
            "exists": True,
            "has_runs": False
        }

    latest = runs[-1]

    return {
        "exists": True,
        "has_runs": True,
        "latest": latest
    }


if __name__ == "__main__":
    status = get_latest_pipeline_status()

    print(json.dumps(status, indent=2, ensure_ascii=False))
