import json
import os
import subprocess
import time
import traceback
from datetime import datetime
from pathlib import Path
from urllib import parse, request


ROOT = Path(__file__).resolve().parents[2]
TASKS_DIR = ROOT / "AI_TASKS"
PENDING_DIR = TASKS_DIR / "pending"
APPROVED_DIR = TASKS_DIR / "approved"
REJECTED_DIR = TASKS_DIR / "rejected"
AGENT_LOGS_DIR = TASKS_DIR / "agent_logs"

BOT_TOKEN = os.environ.get("LEDGERX_TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("LEDGERX_TELEGRAM_CHAT_ID", "").strip()

API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_dirs():
    for folder in [PENDING_DIR, APPROVED_DIR, REJECTED_DIR, AGENT_LOGS_DIR]:
        folder.mkdir(parents=True, exist_ok=True)


def telegram_api(method, data=None):
    if not BOT_TOKEN:
        raise RuntimeError("Missing LEDGERX_TELEGRAM_BOT_TOKEN")

    encoded = parse.urlencode(data or {}).encode("utf-8")
    req = request.Request(f"{API_BASE}/{method}", data=encoded)
    with request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def send_message(text, reply_markup=None):
    data = {
        "chat_id": CHAT_ID,
        "text": text,
    }
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    return telegram_api("sendMessage", data)


def answer_callback(callback_query_id, text="تم"):
    return telegram_api("answerCallbackQuery", {
        "callback_query_id": callback_query_id,
        "text": text,
    })


def make_task_file(task_text):
    task_id = datetime.now().strftime("telegram_task_%Y%m%d_%H%M%S")
    task_path = PENDING_DIR / f"{task_id}.md"
    content = f"""# Telegram AI Task

## Created At
{now()}

## Source
Telegram

## Task
{task_text}
"""
    task_path.write_text(content, encoding="utf-8")
    return task_id, task_path


def run_pipeline(task_id):
    log_path = AGENT_LOGS_DIR / f"{task_id}_railway_worker.json"

    command = [
        "python",
        "AI_SYSTEM/pipelines/AI_DEV_PIPELINE.py",
        "--full",
    ]

    started = now()

    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=900,
    )

    payload = {
        "timestamp": started,
        "finished_at": now(),
        "task_id": task_id,
        "command": " ".join(command),
        "returncode": result.returncode,
        "status": "WAITING_FOR_APPROVAL" if result.returncode == 0 else "FAILED",
        "stdout_tail": (result.stdout or "")[-6000:],
        "stderr_tail": (result.stderr or "")[-6000:],
    }

    log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def send_approval(task_id, pipeline_result):
    if pipeline_result["status"] == "FAILED":
        print("AI PIPELINE FAILED", flush=True)
        print(pipeline_result.get("stdout_tail", ""), flush=True)
        print(pipeline_result.get("stderr_tail", ""), flush=True)

        error_tail = (pipeline_result.get("stderr_tail") or pipeline_result.get("stdout_tail") or "")[-2500:]
        send_message(
            f"❌ AI Task FAILED\n\nTask: {task_id}\n\nآخر سبب ظاهر:\n{error_tail or 'لا يوجد تفاصيل ظاهرة في اللوج'}"
        )
        return

    buttons = {
        "inline_keyboard": [
            [
                {"text": "✅ Approve", "callback_data": f"approve:{task_id}"},
                {"text": "❌ Reject", "callback_data": f"reject:{task_id}"},
            ]
        ]
    }

    send_message(
        f"🧠 AI Task جاهز للمراجعة\n\nTask: {task_id}\nStatus: WAITING_FOR_APPROVAL",
        reply_markup=buttons,
    )


def approve_task(task_id):
    src = PENDING_DIR / f"{task_id}.md"
    dst = APPROVED_DIR / f"{task_id}.md"

    if src.exists():
        src.rename(dst)

    send_message(f"✅ تمت الموافقة على المهمة\n\nTask: {task_id}\n\nسيتم تطبيق مرحلة التنفيذ لاحقًا بأمان.")
    return True


def reject_task(task_id):
    src = PENDING_DIR / f"{task_id}.md"
    dst = REJECTED_DIR / f"{task_id}.md"

    if src.exists():
        src.rename(dst)

    send_message(f"❌ تم رفض المهمة\n\nTask: {task_id}")
    return True


def handle_message(message):
    text = (message.get("text") or "").strip()
    chat_id = str(message.get("chat", {}).get("id", ""))

    if CHAT_ID and chat_id != CHAT_ID:
        return

    if text == "/start":
        send_message("✅ LedgerX AI Cloud Bot جاهز. ابعت /task ثم وصف المهمة.")
        return

    if text.startswith("/task"):
        task_text = text.replace("/task", "", 1).strip()
        if not task_text:
            send_message("اكتب المهمة بعد /task مثال:\n/task عدل شاشة الفواتير")
            return

        task_id, _ = make_task_file(task_text)
        send_message(f"📥 تم استلام المهمة\n\nTask: {task_id}\nجاري تشغيل AI Pipeline...")
        result = run_pipeline(task_id)
        send_approval(task_id, result)
        return

    send_message("استخدم /task ثم اكتب وصف المهمة.")


def handle_callback(callback):
    callback_id = callback.get("id")
    data = callback.get("data", "")

    if data.startswith("approve:"):
        task_id = data.split(":", 1)[1]
        approve_task(task_id)
        answer_callback(callback_id, "Approved")
        return

    if data.startswith("reject:"):
        task_id = data.split(":", 1)[1]
        reject_task(task_id)
        answer_callback(callback_id, "Rejected")
        return


def main():
    ensure_dirs()

    if not BOT_TOKEN:
        raise RuntimeError("LEDGERX_TELEGRAM_BOT_TOKEN is missing")

    if not CHAT_ID:
        raise RuntimeError("LEDGERX_TELEGRAM_CHAT_ID is missing")

    telegram_api("deleteWebhook", {"drop_pending_updates": "true"})

    print("LedgerX Telegram Bot Daemon started.", flush=True)

    offset = None

    while True:
        try:
            data = {
                "timeout": 50,
                "allowed_updates": json.dumps(["message", "callback_query"]),
            }
            if offset is not None:
                data["offset"] = offset

            response = telegram_api("getUpdates", data)

            for update in response.get("result", []):
                offset = update["update_id"] + 1

                if "message" in update:
                    handle_message(update["message"])

                if "callback_query" in update:
                    handle_callback(update["callback_query"])

        except Exception as exc:
            print(f"Daemon error: {exc}", flush=True)
            traceback.print_exc()
            time.sleep(10)


if __name__ == "__main__":
    main()
