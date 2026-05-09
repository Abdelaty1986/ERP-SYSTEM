from pathlib import Path
from datetime import datetime
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
import urllib.error

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NOTIFY_DIR = PROJECT_ROOT / "AI_TASKS" / "notifications"
REJECT_REPORTS = PROJECT_ROOT / "AI_TASKS" / "reject_reports"
STATE_FILE = NOTIFY_DIR / "telegram_bot_daemon_state.json"

NOTIFY_DIR.mkdir(parents=True, exist_ok=True)
REJECT_REPORTS.mkdir(parents=True, exist_ok=True)


def token():
    value = os.environ.get("LEDGERX_TELEGRAM_BOT_TOKEN")
    if not value:
        raise RuntimeError("Missing LEDGERX_TELEGRAM_BOT_TOKEN")
    return value


def chat_id():
    return os.environ.get("LEDGERX_TELEGRAM_CHAT_ID")


def api_get(method):
    url = f"https://api.telegram.org/bot{token()}/{method}"
    with urllib.request.urlopen(url, timeout=35) as r:
        return json.loads(r.read().decode("utf-8"))


def api_post(method, payload):
    url = f"https://api.telegram.org/bot{token()}/{method}"
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=35) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        print(f"Telegram API error in {method}: HTTP {e.code} - {body}")
        return {"ok": False, "error": body}
    except Exception as e:
        print(f"Telegram API error in {method}: {e}")
        return {"ok": False, "error": str(e)}


def send_message(text):
    cid = chat_id()
    if not cid:
        print("Missing LEDGERX_TELEGRAM_CHAT_ID")
        return
    api_post("sendMessage", {"chat_id": cid, "text": text})


def answer_callback(callback_id, text):
    if not callback_id:
        return
    api_post("answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": text,
        "show_alert": "false"
    })


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_update_id": 0, "processed_callbacks": []}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def run(command, timeout=1200):
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def start_agent_for_task(text):
    send_message(f"✅ استلمت المهمة:\n{text}\n\nجاري تحويلها إلى Task وتشغيل AI Agent...")

    intake = run(f'python AI_SYSTEM/intake_engine/arabic_task_intake.py "{text}"', timeout=240)

    if intake.returncode != 0:
        send_message("⚠️ فشل تحويل الرسالة إلى Task. راجع logs.")
        return False

    watcher_state = PROJECT_ROOT / "AI_TASKS" / "agent_logs" / "watcher_state.json"
    if watcher_state.exists():
        watcher_state.unlink()

    subprocess.Popen(
        "python AI_SYSTEM/agent_engine/task_watcher.py",
        cwd=PROJECT_ROOT,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    send_message("🤖 تم تشغيل AI Agent في الخلفية. ستصلك رسالة الموافقة بعد انتهاء الفحص.")
    return True


def approve_apply():
    send_message("✅ تم استلام الموافقة. جاري تطبيق التعديل وتشغيل التحقق...")

    apply_result = run("python AI_SYSTEM/apply_engine/human_approved_apply.py --approve", timeout=600)

    if apply_result.returncode != 0:
        send_message("⚠️ فشل التطبيق أو تم رفضه من طبقات الأمان. راجع apply_reports.")
        return False

    validation = run("python -m py_compile app.py && python AI_SYSTEM/pipelines/AI_DEV_PIPELINE.py --full", timeout=1200)

    if validation.returncode == 0:
        send_message("✅ تم تطبيق التعديل بنجاح، والـ Pipeline نجح.")
        return True

    send_message("⚠️ تم التطبيق لكن التحقق النهائي فشل. راجع التقارير فورًا.")
    return False


def reject_apply(reason="Rejected from Telegram"):
    patch_files = sorted(
        (PROJECT_ROOT / "AI_TASKS" / "generated_patches").glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    task_name = None
    if patch_files:
        try:
            patch_data = json.loads(patch_files[0].read_text(encoding="utf-8"))
            task_name = patch_data.get("task")
        except Exception:
            task_name = None

    if task_name:
        pending = PROJECT_ROOT / "AI_TASKS" / "pending" / task_name
        blocked_dir = PROJECT_ROOT / "AI_TASKS" / "blocked"
        blocked_dir.mkdir(parents=True, exist_ok=True)
        if pending.exists():
            pending.rename(blocked_dir / task_name)

    report = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "REJECTED_BY_HUMAN",
        "reason": reason,
        "task": task_name,
        "source": "telegram_inline_button"
    }
    out = REJECT_REPORTS / f"reject_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    send_message("❌ تم رفض التعديل. تم نقل المهمة إلى blocked ولم يتم تطبيق أي شيء.")
    return True


def handle_update(update):
    state = load_state()
    processed_callbacks = set(state.get("processed_callbacks", []))

    if "callback_query" in update:
        cb = update["callback_query"]
        data = cb.get("data")
        cb_id = cb.get("id")

        if cb_id in processed_callbacks:
            print("Ignored duplicate callback:", cb_id)
            return

        processed_callbacks.add(cb_id)
        state["processed_callbacks"] = list(processed_callbacks)[-100:]
        save_state(state)

        if data == "ledgerx_approve":
            answer_callback(cb_id, "Approval received")
            approve_apply()
            return

        if data == "ledgerx_reject":
            answer_callback(cb_id, "Rejected")
            reject_apply()
            return

    msg = update.get("message") or {}
    text = (msg.get("text") or "").strip()

    if not text:
        return

    if text.startswith("/start"):
        send_message("اكتب المهمة بالشكل ده:\n/task حسّن صفحة AI Dashboard على الموبايل")
        return

    if text.startswith("/task "):
        task_text = text.replace("/task ", "", 1).strip()
        if not task_text:
            send_message("اكتب المهمة بعد /task")
            return
        start_agent_for_task(task_text)
        return

    send_message("لإرسال مهمة استخدم:\n/task اكتب المطلوب بالعربي")


def poll_once():
    state = load_state()
    offset = int(state.get("last_update_id", 0)) + 1

    data = api_get(f"getUpdates?offset={offset}&timeout=10")
    updates = data.get("result", [])

    for update in updates:
        state["last_update_id"] = update["update_id"]
        save_state(state)
        handle_update(update)

    save_state(state)


def main():
    print("LedgerX Telegram Bot Daemon started.")
    print("Press CTRL+C to stop.")
    while True:
        try:
            poll_once()
        except KeyboardInterrupt:
            print("Stopped.")
            break
        except Exception as exc:
            print("Daemon error:", exc)
            time.sleep(5)


if __name__ == "__main__":
    main()
