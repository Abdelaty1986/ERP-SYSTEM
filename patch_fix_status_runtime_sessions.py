from pathlib import Path

p = Path("app.py")
text = p.read_text(encoding="utf-8")

old = '''    api = JarvisMobileRuntimeAPI()
    return jsonify(api.get_status())'''

new = '''    api = JarvisMobileRuntimeAPI()
    status = api.get_status()
    status["runtime_sessions"] = runtime_sessions
    return jsonify(status)'''

if old not in text:
    raise SystemExit("ERROR: target return block not found")

text = text.replace(old, new, 1)
p.write_text(text, encoding="utf-8")

print("✅ fixed mobile status API to include runtime_sessions")
