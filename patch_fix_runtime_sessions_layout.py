from pathlib import Path
import re

path = Path("templates/jarvis/mobile_control_center.html")
text = path.read_text(encoding="utf-8")

# remove broken injected panel first
text = re.sub(
    r'<div class="panel" id="runtime-sessions-panel">.*?</div>\s*</div>',
    '',
    text,
    flags=re.DOTALL
)

panel = '''
<div class="panel runtime-sessions-wrapper" id="runtime-sessions-panel">
  <div class="panel-title">Runtime Sessions</div>

  <div id="runtime-sessions-feed" class="runtime-sessions-feed">
    <div class="runtime-session-card">
      <div class="runtime-session-icon">◉</div>

      <div class="runtime-session-body">
        <div class="runtime-session-title">
          Waiting for runtime telemetry...
        </div>

        <div class="runtime-session-sub">
          No active runtime sessions
        </div>
      </div>

      <div class="runtime-session-status idle">
        idle
      </div>
    </div>
  </div>
</div>
'''

# insert before bottom nav
marker = '<div class="bottom-nav">'
idx = text.find(marker)

if idx != -1:
    text = text[:idx] + panel + "\n" + text[idx:]
else:
    text += panel

# styles
if ".runtime-sessions-wrapper" not in text:

    css = '''
.runtime-sessions-wrapper{
  width:100%;
  margin-top:18px;
}

.runtime-sessions-feed{
  display:flex;
  flex-direction:column;
  gap:12px;
  max-height:420px;
  overflow:auto;
  padding-top:10px;
}

.runtime-session-card{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:14px;
  padding:14px;
  border-radius:18px;
  border:1px solid rgba(0,255,255,.18);
  background:rgba(0,20,40,.45);
}

.runtime-session-icon{
  font-size:20px;
  color:#00e5ff;
}

.runtime-session-body{
  flex:1;
}

.runtime-session-title{
  font-size:15px;
  color:white;
}

.runtime-session-sub{
  font-size:11px;
  opacity:.7;
  margin-top:4px;
  color:#7ee7ff;
}

.runtime-session-status{
  font-size:12px;
  padding:6px 10px;
  border-radius:999px;
  background:rgba(0,255,255,.12);
}

.runtime-session-status.completed{
  color:#00ff9d;
}

.runtime-session-status.active{
  color:#00e5ff;
}

.runtime-session-status.failed{
  color:#ff5b5b;
}

.runtime-session-status.idle{
  color:#aaa;
}
'''

    style_end = text.rfind("</style>")

    if style_end != -1:
        text = text[:style_end] + css + "\n" + text[style_end:]

# upgrade renderer
pattern = r'function renderRuntimeSessions\(data\)\s*\{.*?\n\}'
replacement = r'''
function renderRuntimeSessions(data) {
  const container = document.getElementById("runtime-sessions-feed");

  if (!container) return;

  const sessions = data.runtime_sessions || [];

  if (!sessions.length) {
    container.innerHTML = `
      <div class="runtime-session-card">
        <div class="runtime-session-icon">◉</div>

        <div class="runtime-session-body">
          <div class="runtime-session-title">
            No runtime sessions
          </div>

          <div class="runtime-session-sub">
            Runtime telemetry idle
          </div>
        </div>

        <div class="runtime-session-status idle">
          idle
        </div>
      </div>
    `;
    return;
  }

  container.innerHTML = sessions.slice().reverse().map(session => {
    const status = session.status || "unknown";

    return `
      <div class="runtime-session-card">

        <div class="runtime-session-icon">
          ${status === "completed" ? "✓" : "◉"}
        </div>

        <div class="runtime-session-body">

          <div class="runtime-session-title">
            ${session.command_type || "runtime_session"}
          </div>

          <div class="runtime-session-sub">
            ${session.session_id || ""}
          </div>

          <div class="runtime-session-sub">
            ${session.started_at || ""}
          </div>

        </div>

        <div class="runtime-session-status ${status}">
          ${status}
        </div>

      </div>
    `;
  }).join("");
}
'''

text = re.sub(pattern, replacement, text, flags=re.DOTALL)

path.write_text(text, encoding="utf-8")

print("✅ Runtime Sessions layout fixed")
