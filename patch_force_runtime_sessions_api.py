from pathlib import Path

path = Path("app.py")
text = path.read_text(encoding="utf-8")

import_line = "from jarvis.execution.runtime_session_manager import RuntimeSessionManager\n"
if import_line not in text:
    marker = "from jarvis.execution.runtime_worker_state import RuntimeWorkerState\n"
    if marker in text:
        text = text.replace(marker, marker + import_line)
    else:
        text = import_line + text

route = '@app.route("/jarvis/mobile/api/status")'
idx = text.find(route)
if idx == -1:
    raise SystemExit("ERROR: status route not found")

func_idx = text.find("def ", idx)
next_route = text.find("\n@app.route(", func_idx + 1)
end_idx = next_route if next_route != -1 else len(text)

block = text[func_idx:end_idx]

if "runtime_sessions = RuntimeSessionManager().list_sessions" not in block:
    lines = block.splitlines()
    lines.insert(1, "    runtime_sessions = RuntimeSessionManager().list_sessions(limit=15)")
    block = "\n".join(lines)

if '"runtime_sessions"' not in block:
    targets = [
        '"worker_state": worker_state,',
        "'worker_state': worker_state,",
        '"worker_state": worker_state',
        "'worker_state': worker_state",
    ]

    patched = False
    for t in targets:
        if t in block:
            comma = "," if not t.endswith(",") else ""
            block = block.replace(
                t,
                t + comma + '\n        "runtime_sessions": runtime_sessions,',
                1
            )
            patched = True
            break

    if not patched:
        raise SystemExit("ERROR: could not find worker_state in status response")

text = text[:func_idx] + block + text[end_idx:]
path.write_text(text, encoding="utf-8")

print("✅ forced runtime_sessions into mobile status API")
