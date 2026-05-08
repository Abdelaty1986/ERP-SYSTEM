from pathlib import Path
import json
import os
import urllib.parse
import urllib.request

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NOTIFICATIONS = PROJECT_ROOT / "AI_TASKS" / "notifications"


def latest_notification():
    files = sorted(
        NOTIFICATIONS.glob("approval_required_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    if not files:
        return None, None

    f = files[0]
    return f, json.loads(f.read_text(encoding="utf-8"))


def build_message(data):
    files = data.get("target_files", [])
    files_text = "\n".join([f"- {x}" for x in files]) if files else "- none"

    return f"""🤖 LedgerX AI Approval Required

Task:
{data.get('task')}

Gate:
{data.get('gate_status')}

Operations:
{data.get('operations_count')}

Files:
{files_text}

Approve Command:
{data.get('approve_command')}
"""


def send_telegram(message):
    token = os.environ.get("LEDGERX_TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("LEDGERX_TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Missing Telegram env vars:")
        print("LEDGERX_TELEGRAM_BOT_TOKEN")
        print("LEDGERX_TELEGRAM_CHAT_ID")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=20) as response:
        print(response.read().decode("utf-8"))

    return True


def main():
    f, data = latest_notification()

    if not data:
        print("No approval notification found.")
        return

    message = build_message(data)
    ok = send_telegram(message)

    if ok:
        print("Telegram notification sent.")
        print(f)


if __name__ == "__main__":
    main()
