import json
from pathlib import Path


class IdentityLoader:
    def __init__(self, config_path="JARVIS_CORE/config/jarvis_identity.json"):
        self.config_path = Path(config_path)

    def load_identity(self):
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Jarvis identity config not found: {self.config_path}"
            )

        with open(self.config_path, "r", encoding="utf-8") as file:
            return json.load(file)


if __name__ == "__main__":
    identity = IdentityLoader().load_identity()

    print("Jarvis Identity Loaded:")
    print(f"- Name: {identity['name']}")
    print(f"- Mode: {identity['mode']}")
    print(f"- Wake Word: {identity['voice']['wake_word']}")
    print(f"- Safety Level: {identity['personality']['safety_level']}")
