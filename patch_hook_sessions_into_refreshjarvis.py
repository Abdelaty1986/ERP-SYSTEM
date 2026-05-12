from pathlib import Path

p = Path("templates/jarvis/mobile_control_center.html")
text = p.read_text(encoding="utf-8")

target = "    const data = await res.json();"

# نضيف الربط بعد fetch الخاص بدالة refreshJarvisRuntime فقط
marker = "async function refreshJarvisRuntime(){"
idx = text.find(marker)
if idx == -1:
    raise SystemExit("ERROR: refreshJarvisRuntime not found")

pos = text.find(target, idx)
if pos == -1:
    raise SystemExit("ERROR: data json line not found")

insert_after = pos + len(target)

hook = '''

    try{
      renderRuntimeSessions(data);
    }catch(e){
      console.error("Runtime Sessions render failed", e);
    }
'''

if "Runtime Sessions render failed" not in text:
    text = text[:insert_after] + hook + text[insert_after:]

p.write_text(text, encoding="utf-8")
print("✅ hooked runtime sessions into refreshJarvisRuntime")
