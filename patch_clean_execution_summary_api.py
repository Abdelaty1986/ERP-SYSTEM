from pathlib import Path

p = Path("app.py")
text = p.read_text(encoding="utf-8")

old = '''    sessions = manager.list_registry_sessions(limit=50)

    return jsonify({
        "latest_session": sessions[0] if sessions else None,
        "active_count": len([s for s in sessions if s.get("status") in ["queued", "validating", "running"]]),
        "completed_count": len([s for s in sessions if s.get("status") == "completed"]),
        "failed_count": len([s for s in sessions if s.get("status") == "failed"]),
        "sessions": sessions[:10],
    })'''

new = '''    raw_sessions = manager.list_registry_sessions(limit=50)

    sessions = [
        s for s in raw_sessions
        if not (
            str(s.get("command_id", "")).find("test") != -1 or
            str(s.get("command_type", "")).find("runtime_test") != -1 or
            str(s.get("command_type", "")).find("runtime_transition") != -1
        )
    ]

    return jsonify({
        "latest_session": sessions[0] if sessions else None,
        "active_count": len([s for s in sessions if s.get("status") in ["queued", "validating", "running"]]),
        "completed_count": len([s for s in sessions if s.get("status") == "completed"]),
        "failed_count": len([s for s in sessions if s.get("status") == "failed"]),
        "sessions": sessions[:10],
    })'''

if old not in text:
    raise SystemExit("ERROR: execution summary block not found")

text = text.replace(old, new, 1)
p.write_text(text, encoding="utf-8")

print("✅ execution summary API now filters test sessions")
