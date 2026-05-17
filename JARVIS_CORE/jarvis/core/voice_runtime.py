import subprocess
from jarvis.core.egyptian_voice_prompts import EgyptianVoicePrompts


class JarvisVoiceRuntime:
    """
    Real Arabic/Egyptian voice runtime narrator using Termux TTS.
    """

    def __init__(
        self,
        enabled=True,
        tts_enabled=True,
        dialect="egyptian",
        voice_profile="jarvis_like_arabic",
        speech_rate=0.88,
        speech_pitch=0.82,
    ):
        self.enabled = enabled
        self.tts_enabled = tts_enabled
        self.dialect = dialect
        self.voice_profile = voice_profile
        self.speech_rate = speech_rate
        self.speech_pitch = speech_pitch
        self.prompts = EgyptianVoicePrompts()

    def speak(self, message):
        if not self.enabled:
            return

        if self.tts_enabled:
            try:
                subprocess.run(
                    [
                        "termux-tts-speak",
                        "-r", str(self.speech_rate),
                        "-p", str(self.speech_pitch),
                        message,
                    ],
                    capture_output=True,
                    text=True,
                )
            except Exception:
                pass

    def announce_start(self, task):
        self.speak(self.prompts.start(task))

    def announce_planning(self):
        self.speak(self.prompts.planning())

    def announce_validation(self):
        self.speak(self.prompts.validation())

    def announce_tests(self, passed=True):
        if passed:
            self.speak(self.prompts.tests_passed())
        else:
            self.speak(self.prompts.tests_failed())

    def announce_apply_mode(self, mode):
        if mode == "gated_apply":
            self.speak(self.prompts.gated_mode())
        else:
            self.speak(self.prompts.simulation_mode())

    def announce_completion(self):
        self.speak(self.prompts.completed())

    def announce_blocked(self, reason):
        self.speak(self.prompts.blocked(reason))
