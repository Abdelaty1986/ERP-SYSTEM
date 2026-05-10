import json
from datetime import datetime
from pathlib import Path


class JarvisMemory:
    def __init__(self, memory_path="JARVIS_CORE/memory/jarvis_memory.json"):
        self.memory_path = Path(memory_path)
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self):
        if not self.memory_path.exists():
            return {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "projects": {},
                "decisions": [],
                "preferences": {}
            }

        with open(self.memory_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def save(self, data):
        with open(self.memory_path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def remember_decision(self, project_id, task, decision):
        data = self.load()

        data["decisions"].append({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "project_id": project_id,
            "task": task,
            "decision": decision
        })

        self.save(data)

    def set_preference(self, key, value):
        data = self.load()
        data["preferences"][key] = value
        self.save(data)


if __name__ == "__main__":
    memory = JarvisMemory()

    memory.set_preference("language", "arabic_egyptian")
    memory.remember_decision(
        project_id="ledgerx",
        task="Initialize Jarvis memory system",
        decision="Memory system created successfully"
    )

    print("Jarvis memory saved successfully.")
