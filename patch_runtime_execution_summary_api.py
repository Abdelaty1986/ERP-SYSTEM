from pathlib import Path

p = Path("app.py")
text = p.read_text(encoding="utf-8")

route = '''@app.route("/jarvis/mobile/api/runtime/execution-summary")
def jarvis_mobile_runtime_execution_summary():
    from flask import jsonify

    manager = RuntimeSessionManager()
    sessions = manager.list_registry_sessions(limit=50)

    return jsonify({
        "latest_session": sessions[0] if sessions else None,
        "active_count": len([s for s in sessions if s.get("status") in ["queued", "validating", "running"]]),
        "completed_count": len([s for s in sessions if s.get("status") == "completed"]),
        "failed_count": len([s for s in sessions if s.get("status") == "failed"]),
        "sessions": sessions[:10],
    })
'''

if "/jarvis/mobile/api/runtime/execution-summary" not in text:
    marker = '@app.route("/jarvis/mobile/api/status")'
    idx = text.find(marker)
    if idx == -1:
        raise SystemExit("ERROR: status route marker not found")

    text = text[:idx] + route + "\n" + text[idx:]

p.write_text(text, encoding="utf-8")
print("✅ runtime execution summary API added")
