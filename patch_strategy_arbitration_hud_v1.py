from pathlib import Path

path = Path("templates/jarvis/mobile_control_center.html")
text = path.read_text(encoding="utf-8")

marker = '''
      <div id="decision-alternatives-feed" class="runtime-feed">
        <div class="runtime-empty">Waiting for decision alternatives...</div>
      </div>
    </div>
'''

panel = '''
      <div id="decision-alternatives-feed" class="runtime-feed">
        <div class="runtime-empty">Waiting for decision alternatives...</div>
      </div>
    </div>

    <div class="panel" id="strategy-arbitration-panel">
      <div class="panel-title">Strategy Arbitration</div>
      <div class="panel-sub">Executive strategy tradeoff arbitration</div>

      <div class="metric-row">
        <span>Best Strategy</span>
        <b id="arbitration-best-strategy">loading...</b>
      </div>

      <div class="metric-row">
        <span>Best Score</span>
        <b id="arbitration-best-score">loading...</b>
      </div>

      <div class="metric-row">
        <span>Ranked</span>
        <b id="arbitration-ranked-count">loading...</b>
      </div>

      <div class="runtime-session-sub" style="margin-top:10px">Executive Decision</div>
      <div id="arbitration-decision-feed" class="runtime-feed">
        <div class="runtime-empty">Waiting for arbitration decision...</div>
      </div>

      <div class="runtime-session-sub" style="margin-top:10px">Ranked Strategies</div>
      <div id="arbitration-ranked-feed" class="runtime-feed">
        <div class="runtime-empty">Waiting for ranked strategies...</div>
      </div>
    </div>
'''

if "strategy-arbitration-panel" in text:
    print("strategy arbitration panel already exists")
elif marker not in text:
    raise SystemExit("cognitive decision panel marker not found")
else:
    text = text.replace(marker, panel, 1)
    path.write_text(text, encoding="utf-8")
    print("strategy arbitration HUD panel added")
