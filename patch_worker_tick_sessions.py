from pathlib import Path

path = Path("app.py")
text = path.read_text(encoding="utf-8")

# 1) Ensure import exists
import_line = "from jarvis.execution.runtime_session_manager import RuntimeSessionManager\n"

if import_line not in text:
    marker = "from jarvis.execution.runtime_worker_state import RuntimeWorkerState\n"
    if marker in text:
        text = text.replace(marker, marker + import_line)
    else:
        text = import_line + text

# 2) Locate worker tick route
route = '@app.route("/jarvis/mobile/api/worker/tick", methods=["POST"])'
idx = text.find(route)

if idx == -1:
    raise SystemExit("ERROR: worker tick route not found")

# Find function start after route
func_idx = text.find("def ", idx)
if func_idx == -1:
    raise SystemExit("ERROR: worker tick function not found")

# Find next route after this function
next_route = text.find("\n@app.route(", func_idx + 1)
if next_route == -1:
    end_idx = len(text)
else:
    end_idx = next_route

block = text[func_idx:end_idx]

# 3) If not already patched, add session manager after function line
if "RuntimeSessionManager()" not in block:
    lines = block.splitlines()
    if not lines:
        raise SystemExit("ERROR: empty worker tick block")

    def_line = lines[0]
    rest = lines[1:]

    injected = [
        def_line,
        "    session_manager = RuntimeSessionManager()",
        "    session = session_manager.start_session(",
        '        command_id="runtime_tick",',
        '        command_type="worker_tick",',
        '        source="mobile_hud",',
        "    )",
    ]

    block = "\n".join(injected + rest) + ("\n" if block.endswith("\n") else "")

# 4) Add end_session before JSON success returns
if "worker tick completed" not in block:
    block = block.replace(
        "return jsonify(result)",
        '''session_manager.end_session(
        session["session_id"],
        result="worker tick completed"
    )
    return jsonify(result)'''
    )

    block = block.replace(
        "return jsonify(response)",
        '''session_manager.end_session(
        session["session_id"],
        result="worker tick completed"
    )
    return jsonify(response)'''
    )

# 5) Add failure session inside except blocks if possible
if "worker tick failed" not in block and "except Exception as e:" in block:
    block = block.replace(
        "except Exception as e:",
        '''except Exception as e:
        try:
            session_manager.end_session(
                session["session_id"],
                result="worker tick failed",
                error=str(e)
            )
        except Exception:
            pass'''
    )

text = text[:func_idx] + block + text[end_idx:]
path.write_text(text, encoding="utf-8")

print("✅ patched app.py with RuntimeSessionManager for worker tick")
