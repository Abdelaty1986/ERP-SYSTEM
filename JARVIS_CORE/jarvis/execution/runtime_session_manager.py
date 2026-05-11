import json
import uuid
from pathlib import Path
from datetime import datetime

class RuntimeSessionManager:
    def __init__(self, log_dir="JARVIS_CORE/runtime_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_file = self.log_dir / "runtime_sessions.jsonl"

    def _now(self):
        return datetime.utcnow().isoformat() + "Z"

    def _write(self, session):
        with self.sessions_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(session, ensure_ascii=False) + "\n")

    def start_session(self, command_id=None, command_type=None, source="runtime_worker"):
        session = {
            "session_id": str(uuid.uuid4()),
            "command_id": command_id,
            "command_type": command_type,
            "source": source,
            "status": "active",
            "started_at": self._now(),
            "ended_at": None,
            "result": None,
            "error": None,
        }
        self._write(session)
        return session

    def end_session(self, session_id, result="completed", error=None):
        session = {
            "session_id": session_id,
            "status": "completed" if error is None else "failed",
            "ended_at": self._now(),
            "result": result,
            "error": error,
        }
        self._write(session)
        return session

    def list_sessions(self, limit=20):
        if not self.sessions_file.exists():
            return []

        lines = self.sessions_file.read_text(encoding="utf-8").splitlines()
        sessions = []
        for line in lines[-limit:]:
            try:
                sessions.append(json.loads(line))
            except Exception:
                pass
        return sessions
