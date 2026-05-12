from pathlib import Path

p = Path("templates/jarvis/mobile_control_center.html")
text = p.read_text(encoding="utf-8")

old = '''
refreshExecutionSummary();
refreshRuntimeActivityFeed();
'''

new = '''
refreshExecutionSummary();
refreshRuntimeActivityFeed();

setInterval(() => {
  refreshExecutionSummary();
  refreshRuntimeActivityFeed();
  refreshJarvisRuntime();
}, 5000);
'''

if 'setInterval(() => {' not in text:
    text = text.replace(old, new)

p.write_text(text, encoding="utf-8")

print("✅ runtime live refresh enabled")
