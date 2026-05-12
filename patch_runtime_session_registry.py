from pathlib import Path
import re

path = Path("JARVIS_CORE/jarvis/execution/runtime_session_manager.py")
text = path.read_text(encoding="utf-8")

# add registry file
if 'self.registry_file' not in text:
    text = text.replace(
        'self.sessions_file = self.log_dir / "runtime_sessions.jsonl"',
        '''self.sessions_file = self.log_dir / "runtime_sessions.jsonl"
        self.registry_file = self.log_dir / "runtime_session_registry.json"'''
    )

# add registry updater
if 'def _update_registry' not in text:

    insert = '''

    def _update_registry(self, session):
        registry = {}

        if self.registry_file.exists():
            try:
                registry = json.loads(
                    self.registry_file.read_text(encoding="utf-8")
                )
            except Exception:
                registry = {}

        registry[session["session_id"]] = session

        self.registry_file.write_text(
            json.dumps(registry, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
'''

    idx = text.find("def start_session")
    text = text[:idx] + insert + text[idx:]

# hook registry updates into writer
if 'self._update_registry(session)' not in text:

    text = text.replace(
        'self._write(session)',
        'self._write(session)\n        self._update_registry(session)'
    )

# add active sessions reader
if 'def get_active_sessions' not in text:

    addition = '''

    def get_active_sessions(self):
        if not self.registry_file.exists():
            return []

        try:
            registry = json.loads(
                self.registry_file.read_text(encoding="utf-8")
            )

            return [
                s for s in registry.values()
                if s.get("status") == "active"
            ]

        except Exception:
            return []
'''

    text += addition

path.write_text(text, encoding="utf-8")

print("✅ Runtime Session Registry integrated")
