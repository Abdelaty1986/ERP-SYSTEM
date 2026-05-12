from pathlib import Path

p = Path("JARVIS_CORE/jarvis/execution/runtime_session_manager.py")
text = p.read_text(encoding="utf-8")

if "def list_registry_sessions" not in text:
    insert = '''
    def list_registry_sessions(self, limit=20):

        registry = self._load_registry()

        sessions = list(registry.values())

        sessions = sorted(
            sessions,
            key=lambda item: item.get("started_at") or item.get("ended_at") or "",
            reverse=True
        )

        return sessions[:limit]
'''
    text = text.rstrip() + "\n\n" + insert

p.write_text(text, encoding="utf-8")


app = Path("app.py")
app_text = app.read_text(encoding="utf-8")

app_text = app_text.replace(
    "runtime_sessions = session_manager.list_sessions(limit=15)",
    "runtime_sessions = session_manager.list_registry_sessions(limit=15)"
)

app.write_text(app_text, encoding="utf-8")

print("✅ mobile status now uses runtime session registry")
