from pathlib import Path

path = Path("app.py")
text = path.read_text(encoding="utf-8")

# Ensure import exists
import_line = "from jarvis.execution.runtime_session_manager import RuntimeSessionManager\n"

if import_line not in text:
    marker = "from jarvis.execution.runtime_worker_state import RuntimeWorkerState\n"

    if marker in text:
        text = text.replace(marker, marker + import_line)
    else:
        text = import_line + text

# Locate status route
route = '@app.route("/jarvis/mobile/api/status")'
idx = text.find(route)

if idx == -1:
    raise SystemExit("ERROR: status API route not found")

# Find function block
func_idx = text.find("def ", idx)

next_route = text.find("\n@app.route(", func_idx + 1)
if next_route == -1:
    end_idx = len(text)
else:
    end_idx = next_route

block = text[func_idx:end_idx]

# Prevent duplicate patch
if "runtime_sessions" not in block:

    # inject manager after function definition
    lines = block.splitlines()

    def_line = lines[0]
    rest = lines[1:]

    injected = [
        def_line,
        "    session_manager = RuntimeSessionManager()",
        "    runtime_sessions = session_manager.list_sessions(limit=15)",
    ]

    block = "\n".join(injected + rest)

    # add runtime_sessions to API responses
    block = block.replace(
        '"worker_state": worker_state,',
        '''"worker_state": worker_state,
        "runtime_sessions": runtime_sessions,'''
    )

    block = block.replace(
        "'worker_state': worker_state,",
        ''''worker_state': worker_state,
        'runtime_sessions': runtime_sessions,'''
    )

text = text[:func_idx] + block + text[end_idx:]

path.write_text(text, encoding="utf-8")

print("✅ Runtime Sessions API integrated")
