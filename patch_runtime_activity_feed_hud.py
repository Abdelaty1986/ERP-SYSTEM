from pathlib import Path

p = Path("templates/jarvis/mobile_control_center.html")
text = p.read_text(encoding="utf-8")

panel = '''
<div class="panel" id="runtime-activity-feed-panel">
  <div class="panel-title">Runtime Activity Feed</div>

  <div id="runtime-activity-feed" class="runtime-sessions-feed">
    <div class="runtime-session-card">
      <div class="runtime-session-icon">◉</div>
      <div class="runtime-session-body">
        <div class="runtime-session-title">Waiting for runtime activity...</div>
        <div class="runtime-session-sub">Telemetry stream idle</div>
      </div>
      <div class="runtime-session-status idle">idle</div>
    </div>
  </div>
</div>
'''

if 'id="runtime-activity-feed-panel"' not in text:
    marker = '<div class="panel runtime-sessions-wrapper" id="runtime-sessions-panel">'
    idx = text.find(marker)
    if idx != -1:
        text = text[:idx] + panel + "\n" + text[idx:]
    else:
        text += panel

js = '''
async function refreshRuntimeActivityFeed(){
  try{
    const res = await fetch("/jarvis/mobile/api/runtime/activity-feed");
    const data = await res.json();
    const container = document.getElementById("runtime-activity-feed");

    if(!container) return;

    const feed = data.feed || [];

    if(!feed.length){
      container.innerHTML = `
        <div class="runtime-session-card">
          <div class="runtime-session-icon">◉</div>
          <div class="runtime-session-body">
            <div class="runtime-session-title">No runtime activity</div>
            <div class="runtime-session-sub">Telemetry stream idle</div>
          </div>
          <div class="runtime-session-status idle">idle</div>
        </div>
      `;
      return;
    }

    container.innerHTML = feed.map(item => {
      const status = item.status || "unknown";
      return `
        <div class="runtime-session-card">
          <div class="runtime-session-icon">${status === "completed" ? "✓" : "◉"}</div>
          <div class="runtime-session-body">
            <div class="runtime-session-title">[${status.toUpperCase()}] ${item.command_type || "runtime"}</div>
            <div class="runtime-session-sub">${item.result || item.command_id || ""}</div>
            <div class="runtime-session-sub">${item.timestamp || ""}</div>
          </div>
          <div class="runtime-session-status ${status}">${status}</div>
        </div>
      `;
    }).join("");
  }catch(e){
    console.error("Runtime activity feed refresh failed", e);
  }
}
'''

if "async function refreshRuntimeActivityFeed" not in text:
    script_end = text.rfind("</script>")
    if script_end != -1:
        text = text[:script_end] + js + "\n" + text[script_end:]

if "refreshRuntimeActivityFeed();" not in text:
    text = text.replace(
        "refreshExecutionSummary();",
        "refreshExecutionSummary();\nrefreshRuntimeActivityFeed();",
        1
    )

p.write_text(text, encoding="utf-8")
print("✅ runtime activity feed HUD panel added")
