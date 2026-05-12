from pathlib import Path

path = Path("templates/jarvis/mobile_control_center.html")
text = path.read_text(encoding="utf-8")

old = 'const sessions = data.runtime_sessions || [];'
new = '''
  const sessions = (data.runtime_sessions || []).filter(session => {
    const commandId = session.command_id || "";
    const commandType = session.command_type || "";

    return !(
      commandId.includes("test") ||
      commandType.includes("runtime_test") ||
      commandType.includes("runtime_transition")
    );
  });
'''

if old not in text:
    raise SystemExit("ERROR: sessions line not found")

text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")

print("✅ runtime sessions HUD now filters test sessions")
