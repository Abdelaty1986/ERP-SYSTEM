from pathlib import Path
import re

path = Path("app.py")
text = path.read_text(encoding="utf-8")

route = '@app.route("/jarvis/mobile/api/worker/tick", methods=["POST"])'
idx = text.find(route)

if idx == -1:
    raise SystemExit("ERROR: worker tick route not found")

func_idx = text.find("def ", idx)

next_route = text.find("\n@app.route(", func_idx + 1)
end_idx = next_route if next_route != -1 else len(text)

block = text[func_idx:end_idx]

# queued transition after start_session
if 'transition_session(session["session_id"], "validating")' not in block:

    marker = '''session = session_manager.start_session(
        command_id="runtime_tick",
        command_type="worker_tick",
        source="mobile_hud",
    )'''

    replacement = marker + '''

    session_manager.transition_session(
        session["session_id"],
        "validating"
    )'''

    block = block.replace(marker, replacement)

# running transition before processing result
if '"running"' not in block:

    target = "result ="

    pos = block.find(target)

    if pos != -1:
        insert = '''

    session_manager.transition_session(
        session["session_id"],
        "running"
    )

'''

        block = block[:pos] + insert + block[pos:]

# completed transition
block = re.sub(
    r'session_manager\.end_session\(\s*session\["session_id"\],\s*result="worker tick completed"\s*\)',
    '''session_manager.transition_session(
        session["session_id"],
        "completed",
        result="worker tick completed"
    )''',
    block,
    flags=re.DOTALL
)

# failed transition
block = re.sub(
    r'session_manager\.end_session\(\s*session\["session_id"\],\s*result="worker tick failed",\s*error=str\(e\)\s*\)',
    '''session_manager.transition_session(
                session["session_id"],
                "failed",
                result="worker tick failed",
                error=str(e)
            )''',
    block,
    flags=re.DOTALL
)

text = text[:func_idx] + block + text[end_idx:]

path.write_text(text, encoding="utf-8")

print("✅ worker lifecycle transitions connected")
