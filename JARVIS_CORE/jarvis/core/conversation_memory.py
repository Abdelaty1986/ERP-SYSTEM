from datetime import datetime


class ConversationMemory:
    def __init__(self, max_history=20):
        self.max_history = max_history
        self.history = []

    def add(self, role, message):
        self.history.append({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "role": role,
            "message": message
        })

        if len(self.history) > self.max_history:
            self.history.pop(0)

    def get_history(self):
        return self.history

    def clear(self):
        self.history = []


if __name__ == "__main__":
    memory = ConversationMemory()

    memory.add("user", "جارفيس")
    memory.add("assistant", "نعم يا هاني، سامعك.")
    memory.add("user", "راجع المشروع")

    for item in memory.get_history():
        print(item)
