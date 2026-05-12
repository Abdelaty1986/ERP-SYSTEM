from pathlib import Path

path = Path("JARVIS_CORE/jarvis/execution/runtime_session_manager.py")
text = path.read_text(encoding="utf-8")

# add transition updater
if "def transition_session" not in text:

    addition = '''

    def transition_session(
        self,
        session_id,
        status,
        result=None,
        error=None
    ):

        registry = self._load_registry()

        session = registry.get(session_id)

        if not session:
            return None

        session["status"] = status

        if result is not None:
            session["result"] = result

        if error is not None:
            session["error"] = error

        if status in ["completed", "failed"]:
            session["ended_at"] = self._now()

        self._write(session)
        self._update_registry(session)

        return session
'''

    text += addition

# make new sessions start queued instead of active
text = text.replace(
    '"status": "active"',
    '"status": "queued"',
    1
)

path.write_text(text, encoding="utf-8")

print("✅ runtime lifecycle transitions integrated")
