import subprocess


class JarvisVoiceRuntime:
    """
    Real voice runtime narrator using Termux TTS.
    """

    def __init__(self, enabled=True, tts_enabled=True):
        self.enabled = enabled
        self.tts_enabled = tts_enabled

    def speak(self, message):
        if not self.enabled:
            return

        print(f"[JARVIS]: {message}")

        if self.tts_enabled:
            try:
                subprocess.run(
                    ["termux-tts-speak", message],
                    capture_output=True,
                    text=True,
                )
            except Exception:
                pass

    def announce_start(self, task):
        self.speak(f"Initializing runtime for task: {task}")

    def announce_planning(self):
        self.speak("Planning execution steps.")

    def announce_validation(self):
        self.speak("Validating generated patches.")

    def announce_tests(self, passed=True):
        if passed:
            self.speak("All runtime tests passed.")
        else:
            self.speak("Runtime tests failed.")

    def announce_apply_mode(self, mode):
        self.speak(f"Execution mode: {mode}")

    def announce_completion(self):
        self.speak("Execution completed successfully.")

    def announce_blocked(self, reason):
        self.speak(f"Execution blocked: {reason}")
