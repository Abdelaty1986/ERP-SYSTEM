class IntentDetector:

    GENERAL_CHAT = "general_chat"
    DEVELOPMENT_TASK = "development_task"
    STOP_COMMAND = "stop_command"

    DEVELOPMENT_KEYWORDS = [
        "راجع",
        "عدل",
        "طور",
        "اختبر",
        "شغل",
        "افتح",
        "اصلح",
        "نفذ",
        "حلل",
        "راقب",
        "ابني"
    ]

    STOP_KEYWORDS = [
        "اسكت",
        "نام",
        "توقف",
        "اقفل"
    ]

    def detect(self, text):
        lowered = text.strip().lower()

        for word in self.STOP_KEYWORDS:
            if word in lowered:
                return self.STOP_COMMAND

        for word in self.DEVELOPMENT_KEYWORDS:
            if word in lowered:
                return self.DEVELOPMENT_TASK

        return self.GENERAL_CHAT


if __name__ == "__main__":
    detector = IntentDetector()

    tests = [
        "انت تعرف انت ايه",
        "راجع المشروع",
        "اسكت"
    ]

    for item in tests:
        print(item)
        print(detector.detect(item))
        print("-" * 40)
