from datetime import datetime
from jarvis.core.memory import JarvisMemory


class LearningSuggestions:
    def __init__(self):
        self.memory = JarvisMemory()

    def analyze_message(self, text):
        suggestions = []

        lowered = text.strip().lower()

        if "منظم" in lowered or "كركبة" in lowered:
            suggestions.append(
                "User prefers clean and organized architecture."
            )

        if "بالترتيب" in lowered:
            suggestions.append(
                "User prefers step-by-step execution."
            )

        if "مجاني" in lowered:
            suggestions.append(
                "User prefers free-only AI agents and tools."
            )

        if "بدون اخطاء" in lowered or "الأخطاء" in lowered:
            suggestions.append(
                "User prioritizes stability and low-risk execution."
            )

        return suggestions

    def save_pending_suggestions(self, text):
        data = self.memory.load()

        learning = data.setdefault("learning", {})
        pending = learning.setdefault("pending_suggestions", [])

        suggestions = self.analyze_message(text)

        for suggestion in suggestions:
            exists = any(
                item["suggestion"] == suggestion
                for item in pending
            )

            if not exists:
                pending.append({
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "source_text": text,
                    "suggestion": suggestion,
                    "approved": False
                })

        self.memory.save(data)

        return pending


if __name__ == "__main__":
    learner = LearningSuggestions()

    learner.save_pending_suggestions(
        "عايز جارفيس يكون منظم ومن غير كركبة"
    )

    print("Pending learning suggestions saved safely.")
