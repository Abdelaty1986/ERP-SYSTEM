import os
import subprocess
import tempfile
import time


DEFAULT_DURATION = 15
DEFAULT_LIMIT = 5


class MicRecorder:
    def __init__(self, duration=DEFAULT_DURATION, silence_limit=DEFAULT_LIMIT):
        self.duration = duration
        self.silence_limit = silence_limit

    def record(self, duration=None):
        record_secs = duration or self.duration
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()

        try:
            subprocess.run(
                [
                    "termux-microphone-record",
                    "-f", tmp.name,
                    "-d", str(record_secs),
                    "-l", str(self.silence_limit),
                ],
                check=True, timeout=record_secs + 10,
            )
            if not os.path.getsize(tmp.name):
                raise RuntimeError("Recorded file is empty")
            return tmp.name
        except subprocess.CalledProcessError as exc:
            os.unlink(tmp.name)
            raise RuntimeError(f"termux-microphone-record failed: {exc}") from exc


def record_voice(duration=10):
    recorder = MicRecorder(duration=duration)
    print("[MIC] تسجيل الصوت...")
    path = recorder.record()
    print(f"[MIC] تم التسجيل: {path}")
    return path


if __name__ == "__main__":
    path = record_voice(duration=5)
    print(f"Saved to {path}")
