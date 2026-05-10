class VoiceManager:
    def __init__(self, wake_word="جارفيس"):
        self.wake_word = wake_word
        self.listening = False

    def detect_wake_word(self, text):
        return self.wake_word in text

    def start_listening(self):
        self.listening = True

    def stop_listening(self):
        self.listening = False

    def process_input(self, text):
        if not self.listening:
            if self.detect_wake_word(text):
                self.start_listening()

                return {
                    "wake_detected": True,
                    "response": "نعم يا هاني، سامعك."
                }

            return {
                "wake_detected": False,
                "response": None
            }

        if "اسكت" in text or "نام" in text:
            self.stop_listening()

            return {
                "wake_detected": False,
                "response": "تم إيقاف الاستماع."
            }

        return {
            "wake_detected": False,
            "response": f"تم استلام الأمر: {text}"
        }


if __name__ == "__main__":
    voice = VoiceManager()

    tests = [
        "مرحبا",
        "جارفيس",
        "راجع المشروع",
        "اسكت"
    ]

    for item in tests:
        print(f"Input: {item}")
        print(voice.process_input(item))
        print("-" * 40)
