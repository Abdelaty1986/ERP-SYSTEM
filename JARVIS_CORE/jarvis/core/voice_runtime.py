class JarvisVoiceRuntime:
    """
    Lightweight voice-style runtime narrator for JARVIS CLI.
    Currently text-based and safe for terminal environments.
    """

    def __init__(self, enabled=True):
        self.enabled = enabled

    def speak(self, message):
        if not self.enabled:
            return

        print(f"[JARVIS]: {message}")

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
