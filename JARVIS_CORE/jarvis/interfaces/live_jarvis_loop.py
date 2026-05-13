from __future__ import annotations

from pathlib import Path

from jarvis.core.conversation_brain import ConversationBrain
from jarvis.core.voice_runtime import JarvisVoiceRuntime
from jarvis.execution.sandbox_execution_report import SandboxExecutionReport


class LiveJarvisLoop:
    """
    Interactive Jarvis loop.
    Jarvis responds from inside the runtime.
    Real apply remains disabled.
    """

    def __init__(self, tts_enabled=False):
        self.brain = ConversationBrain()
        self.voice = JarvisVoiceRuntime(
            enabled=True,
            tts_enabled=tts_enabled,
        )
        self.running = True

    def _speak(self, message):
        print(f"JARVIS: {message}")
        self.voice.speak(message)

    def _is_runtime_command(self, text):
        keywords = [
            "راجع",
            "افحص",
            "اختبر",
            "حلل",
            "sandbox",
            "الوضع الآمن",
            "النظام",
            "runtime",
        ]
        return any(word in text for word in keywords)

    def _run_safe_runtime(self, text):
        target = Path("JARVIS_CORE/jarvis/runtime/runtime_audit.py")
        original = target.read_text(encoding="utf-8")

        report = SandboxExecutionReport().run(
            task=text,
            file_path=str(target),
            proposed_content=(
                original
                + "\n# live_jarvis_loop_sandbox_marker\n"
            ),
            human_approval=None,
        )

        final_state = report.get("final_state")
        sandbox_ok = report.get("sandbox", {}).get("apply", {}).get("ok")
        tests_ok = report.get("sandbox", {}).get("post_test", {}).get("ok")
        original_modified = report.get("original_files_modified")
        approval_status = report.get("approval", {}).get("status")

        return (
            "تم تشغيل المهمة في الوضع الآمن.\n"
            f"حالة التقرير: {final_state}\n"
            f"Sandbox: {'ناجح' if sandbox_ok else 'يحتاج مراجعة'}\n"
            f"الاختبارات: {'ناجحة' if tests_ok else 'فشلت'}\n"
            f"الملف الأصلي اتعدل؟ {original_modified}\n"
            f"حالة الموافقة: {approval_status}\n"
            "لم يتم تنفيذ أي تعديل حقيقي."
        )

    def handle(self, text):
        normalized = text.strip()

        if not normalized:
            return "مسمعتش أمر واضح."

        if normalized in {"خروج", "انهاء", "اقفل", "نام"}:
            self.running = False
            return "تم إيقاف جلسة جارفيس."

        if normalized in {"حالتك", "انت شغال", "عامل ايه", "جاهز"}:
            return (
                "أنا شغال في الوضع الآمن. "
                "أقدر أراجع وأحلل وأعمل Sandbox Report، "
                "لكن لا أطبق تعديلات حقيقية بدون موافقة."
            )

        if self._is_runtime_command(normalized):
            return self._run_safe_runtime(normalized)

        brain_result = self.brain.respond(normalized)
        return brain_result.get(
            "response",
            "استلمت كلامك، لكن محتاج أمر أوضح."
        )

    def run(self):
        self._speak("أنا جاهز يا هاني. جارفيس يعمل الآن في الوضع الآمن.")

        while self.running:
            try:
                text = input("YOU: ").strip()
                response = self.handle(text)
                self._speak(response)
            except KeyboardInterrupt:
                self._speak("تم إيقاف الجلسة.")
                break
            except Exception as exc:
                self._speak(f"حدث خطأ أثناء التشغيل: {exc}")


if __name__ == "__main__":
    LiveJarvisLoop(tts_enabled=False).run()
