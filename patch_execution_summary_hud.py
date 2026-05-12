from pathlib import Path

p = Path("templates/jarvis/mobile_control_center.html")
text = p.read_text(encoding="utf-8")

panel = '''
<div class="panel" id="runtime-execution-summary-panel">
  <div class="panel-title">Execution Summary</div>

  <div class="mini-grid">
    <div class="mini-card">
      <div id="runtime-active-count">0</div>
      <span>Active</span>
    </div>
    <div class="mini-card">
      <div id="runtime-completed-count">0</div>
      <span>Completed</span>
    </div>
    <div class="mini-card">
      <div id="runtime-failed-count">0</div>
      <span>Failed</span>
    </div>
  </div>

  <div class="panel-sub" id="runtime-latest-session">
    Latest session: none
  </div>
</div>
'''

if 'id="runtime-execution-summary-panel"' not in text:
    marker = '<div class="panel runtime-sessions-wrapper" id="runtime-sessions-panel">'
    idx = text.find(marker)
    if idx != -1:
        text = text[:idx] + panel + "\n" + text[idx:]
    else:
        text += panel

js = '''
async function refreshExecutionSummary(){
  try{
    const res = await fetch("/jarvis/mobile/api/runtime/execution-summary");
    const data = await res.json();

    const active = document.getElementById("runtime-active-count");
    const completed = document.getElementById("runtime-completed-count");
    const failed = document.getElementById("runtime-failed-count");
    const latest = document.getElementById("runtime-latest-session");

    if(active) active.textContent = data.active_count ?? 0;
    if(completed) completed.textContent = data.completed_count ?? 0;
    if(failed) failed.textContent = data.failed_count ?? 0;

    if(latest && data.latest_session){
      latest.textContent = "Latest: " + (data.latest_session.command_type || "runtime") + " / " + data.latest_session.status;
    }
  }catch(e){
    console.error("Execution summary refresh failed", e);
  }
}
'''

if "async function refreshExecutionSummary" not in text:
    script_end = text.rfind("</script>")
    if script_end != -1:
        text = text[:script_end] + js + "\n" + text[script_end:]

if "refreshExecutionSummary();" not in text:
    text = text.replace(
        "refreshJarvisRuntime();",
        "refreshJarvisRuntime();\nrefreshExecutionSummary();",
        1
    )

p.write_text(text, encoding="utf-8")
print("✅ execution summary HUD panel added")
