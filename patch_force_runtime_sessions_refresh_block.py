from pathlib import Path
import re

p = Path("templates/jarvis/mobile_control_center.html")
text = p.read_text(encoding="utf-8")

pattern = r'async function refreshRuntimeStatus\(\)\s*\{.*?const data = await res\.json\(\);'

replacement = r'''async function refreshRuntimeStatus() {
  try {
    const res = await fetch("/jarvis/mobile/api/status");
    const data = await res.json();

    try {
      renderRuntimeSessions(data);
    } catch (e) {
      console.log("runtime sessions render error", e);
    }
'''

new_text = re.sub(pattern, replacement, text, flags=re.DOTALL)

if new_text == text:
    raise SystemExit("ERROR: refreshRuntimeStatus block not found")

p.write_text(new_text, encoding="utf-8")

print("✅ forced runtime sessions render inside refreshRuntimeStatus")
