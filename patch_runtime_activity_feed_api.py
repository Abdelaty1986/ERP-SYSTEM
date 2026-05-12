from pathlib import Path

p = Path("app.py")
text = p.read_text(encoding="utf-8")

route = '''@app.route("/jarvis/mobile/api/runtime/activity-feed")
def jarvis_mobile_runtime_activity_feed():
    from flask import jsonify

    manager = RuntimeSessionManager()
    raw_sessions = manager.list_registry_sessions(limit=30)

    sessions = [
        s for s in raw_sessions
        if not (
            "test" in str(s.get("command_id", "")) or
            "runtime_test" in str(s.get("command_type", "")) or
            "runtime_transition" in str(s.get("command_type", ""))
        )
    ]

    feed = []
    for session in sessions[:15]:
        feed.append({
            "status": session.get("status", "unknown"),
            "command_type": session.get("command_type", "runtime"),
            "command_id": session.get("command_id", ""),
            "session_id": session.get("session_id", ""),
            "timestamp": session.get("ended_at") or session.get("started_at"),
            "result": session.get("result"),
            "error": session.get("error"),
        })

    return jsonify({
        "count": len(feed),
        "feed": feed,
    })
'''

if "/jarvis/mobile/api/runtime/activity-feed" not in text:
    marker = '@app.route("/jarvis/mobile/api/runtime/execution-summary")'
    idx = text.find(marker)
    if idx == -1:
        raise SystemExit("ERROR: execution summary route marker not found")

    text = text[:idx] + route + "\n" + text[idx:]

p.write_text(text, encoding="utf-8")
print("✅ runtime activity feed API added")
