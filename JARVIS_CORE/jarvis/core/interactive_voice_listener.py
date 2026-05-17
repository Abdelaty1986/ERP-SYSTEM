import subprocess

from jarvis.core.orchestrator import Orchestrator
from jarvis.core.voice_runtime import JarvisVoiceRuntime


class InteractiveVoiceListener:
    """
    Voice-controlled JARVIS runtime listener.
    """

    BLOCKED_OUTPUTS = {
        "ERROR: ERROR_NO_MATCH",
        "ERROR: ERROR_SPEECH_TIMEOUT",
        "ERROR: ERROR_CLIENT",
    }

    def __init__(self):
        self.orchestrator = Orchestrator()
        self.voice = JarvisVoiceRuntime(enabled=True, tts_enabled=True)

    def listen(self):
        print("[JARVIS]: أنا سامعك يا هاني. قول الأمر دلوقتي.")
        self.voice.speak("أنا سامعك يا هاني. قول الأمر دلوقتي.")

        try:
            result = subprocess.run(
                ["termux-speech-to-text"],
                capture_output=True,
                text=True,
            )

            task = result.stdout.strip()

            if (
                not task
                or task.startswith("ERROR:")
                or task in self.BLOCKED_OUTPUTS
            ):
                print("[JARVIS]: مسمعتش الأمر بوضوح. حاول تاني.")
                self.voice.speak("مسمعتش الأمر بوضوح. حاول تاني.")
                return {
                    "status": "no_valid_voice_command",
                    "ok": False,
                    "raw": task,
                }

            print(f"[USER]: {task}")

            self.voice.speak(f"تمام. استلمت الأمر: {task}")

            report = self.orchestrator.process_task(
                task,
                human_approval=None,
            )

            return {
                "status": "executed",
                "ok": True,
                "task": task,
                "report": report,
            }

        except Exception as exc:
            self.voice.speak("حصل خطأ في وضع الاستماع.")
            print(f"[JARVIS]: Voice listener failed: {exc}")
            return {
                "status": "failed",
                "ok": False,
                "error": str(exc),
            }


if __name__ == "__main__":
    InteractiveVoiceListener().listen()
