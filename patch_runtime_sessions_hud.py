from pathlib import Path

path = Path("templates/jarvis/mobile_control_center.html")
text = path.read_text(encoding="utf-8")

if 'id="runtime-sessions-feed"' not in text:

    panel = '''
    <div class="panel" id="runtime-sessions-panel">
      <div class="panel-title">Runtime Sessions</div>

      <div id="runtime-sessions-feed">
        <div class="task">
          <div>◉</div>
          <div>
            Waiting for runtime sessions...
            <div class="panel-sub">No active telemetry</div>
          </div>
          <div>idle</div>
        </div>
      </div>
    </div>
'''

    # inject after worker panel if found
    marker = 'id="task-queue-panel"'

    idx = text.find(marker)

    if idx != -1:
        insert_at = text.find("</div>", idx)
        insert_at = text.find("</div>", insert_at + 1)
        insert_at = text.find("</div>", insert_at + 1)

        text = text[:insert_at + 6] + "\n" + panel + text[insert_at + 6:]
    else:
        text += "\n" + panel

# Inject JS renderer
if "renderRuntimeSessions" not in text:

    js = '''

function renderRuntimeSessions(data) {
  const container = document.getElementById("runtime-sessions-feed");

  if (!container) return;

  const sessions = data.runtime_sessions || [];

  if (!sessions.length) {
    container.innerHTML = `
      <div class="task">
        <div>◉</div>
        <div>
          No runtime sessions
          <div class="panel-sub">Telemetry idle</div>
        </div>
        <div>idle</div>
      </div>
    `;
    return;
  }

  container.innerHTML = sessions.slice().reverse().map(session => {
    const status = session.status || "unknown";

    return `
      <div class="task">
        <div>${status === "completed" ? "✓" : "◉"}</div>

        <div>
          ${session.command_type || "runtime_session"}

          <div class="panel-sub">
            ${session.session_id || "no-session-id"}
          </div>

          <div class="panel-sub">
            ${session.started_at || ""}
          </div>
        </div>

        <div>${status}</div>
      </div>
    `;
  }).join("");
}
'''

    # append before closing script
    script_end = text.rfind("</script>")

    if script_end == -1:
        text += f"\n<script>\n{js}\n</script>\n"
    else:
        text = text[:script_end] + js + "\n" + text[script_end:]

# Hook into existing refresh
if "renderRuntimeSessions(data);" not in text:

    text = text.replace(
        "renderWorkerState(data);",
        "renderWorkerState(data);\n        renderRuntimeSessions(data);"
    )

path.write_text(text, encoding="utf-8")

print("✅ Runtime Sessions HUD feed integrated")
