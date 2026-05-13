from pathlib import Path
from datetime import datetime
import json

class RuntimeContinuityMemory:
    def __init__(self, root="."):
        self.root = Path(root)
        self.memory_dir = self.root / "JARVIS_CORE" / "runtime_logs"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.memory_file = self.memory_dir / "runtime_continuity_memory.json"

    def persist(self, identity_data):
        state = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "bounded": True,
            "mode": "runtime_continuity_memory",
            "autonomous_apply": False,
            "identity": identity_data.get("identity", {}),
            "current_state": identity_data.get("current_state", {}),
            "continuity": identity_data.get("continuity", {}),
            "self_description": identity_data.get("self_description"),
        }

        self.memory_file.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return self.read()

    def read(self):
        if not self.memory_file.exists():
            return {
                "bounded": True,
                "mode": "runtime_continuity_memory",
                "autonomous_apply": False,
                "state": "empty",
                "message": "No runtime continuity memory available yet."
            }

        try:
            data = json.loads(self.memory_file.read_text(encoding="utf-8"))
            return {
                "bounded": True,
                "mode": "runtime_continuity_memory",
                "autonomous_apply": False,
                "state": "restored",
                "continuity_memory": data,
                "notes": [
                    "Runtime continuity memory restores the last cognitive runtime state.",
                    "This layer is persistence-only.",
                    "No autonomous execution is performed."
                ]
            }

        except Exception as exc:
            return {
                "bounded": True,
                "mode": "runtime_continuity_memory",
                "autonomous_apply": False,
                "state": "corrupted",
                "error": str(exc)
            }
