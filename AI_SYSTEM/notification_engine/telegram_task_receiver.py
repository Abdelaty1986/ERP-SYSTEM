from pathlib import Path
from datetime import datetime
import json
import os
import subprocess
import urllib.request

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_FILE = PROJECT_ROOT / "AI_TASKS" / "notifications" / "telegram_receiver_state.json"
LOG_DIR = PROJECT_ROOT / "AI_TASKS" / "notifications"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def tg_api(method):
    token = os.environ.get("LEDGERX_TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing LEDGERX_TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/{method}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"last_update_id": 0}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def run(command):
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        shell=True,
        capture_output=True,
        text=True,
        timeout=900,
    )


def send_message(text):
    token = os.environ.get("LEDGERX_TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("LEDGERX_TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    import urllib.parse
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data, method="POST")
    urllib.request.urlopen(req, timeout=30).read()


def main():
    state = load_state()
    offset = int(state.get("last_update_id", 0)) + 1

    data = tg_api(f"getUpdates?offset={offset}&timeout=3")
    updates = data.get("result", [])

    if not updates:
        print("No new Telegram tasks.")
        return

    for update in updates:
        state["last_update_id"] = update["update_id"]

        message = update.get("message") or {}
        text = (message.get("text") or "").strip()

        if not text:
            continue

        if text.startswith("/start"):
            send_message("اكتب المهمة بهذا الشكل:\n/task حسّن شكل صفحة AI Dashboard على الموبايل")
            continue

        if not text.startswith("/task "):
            print("Ignored non-task message:", text)
            continue

        text = text.replace("/task ", "", 1).strip()

        if not text:
            send_message("اكتب المهمة بعد /task")
            continue

        send_message(f"✅ استلمت المهمة:\n{text}\n\nجاري تحويلها إلى Task وتشغيل AI Agent...")

        intake = run(f'python AI_SYSTEM/intake_engine/arabic_task_intake.py "{text}"')
        import subprocess

        watcher = subprocess.Popen(
            "python AI_SYSTEM/agent_engine/task_watcher.py",
            cwd=PROJECT_ROOT,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        log = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "telegram_text": text,
            "intake_ok": intake.returncode == 0,
            "watcher_started": True,
            "intake_stdout": intake.stdout[-3000:],
            "intake_stderr": intake.stderr[-3000:],
        }

        out = LOG_DIR / f"telegram_task_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        out.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")

        send_message("🤖 تم تشغيل AI Agent لمعالجة المهمة. ستصلك رسالة موافقة تلقائيًا بعد انتهاء الفحص.")

    save_state(state)
    print("Telegram tasks processed.")


if __name__ == "__main__":
    main()
