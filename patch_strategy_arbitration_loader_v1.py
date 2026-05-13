from pathlib import Path

path = Path("templates/jarvis/mobile_control_center.html")
text = path.read_text(encoding="utf-8")

script = r'''
<script>
async function loadStrategyArbitrationSnapshot() {
  const bestEl = document.getElementById("arbitration-best-strategy");
  const scoreEl = document.getElementById("arbitration-best-score");
  const rankedCountEl = document.getElementById("arbitration-ranked-count");
  const decisionEl = document.getElementById("arbitration-decision-feed");
  const rankedEl = document.getElementById("arbitration-ranked-feed");

  if (!bestEl || !scoreEl || !rankedCountEl || !decisionEl || !rankedEl) return;

  try {
    const res = await fetch("/jarvis/mobile/api/architecture/arbitration");
    const data = await res.json();

    const summary = data.summary || {};
    const exec = data.executive_decision || {};
    const ranked = Array.isArray(data.ranked_strategies) ? data.ranked_strategies : [];

    bestEl.textContent = summary.best_strategy || "unknown";
    scoreEl.textContent = summary.best_arbitration_score ?? 0;
    rankedCountEl.textContent = summary.strategies_ranked ?? ranked.length;

    decisionEl.innerHTML = `
      <div class="runtime-event runtime-insight-card severity-high">
        <div class="runtime-event-main">${exec.strategy || "n/a"} · ${exec.execution_preference || "n/a"}</div>
        <div class="runtime-event-sub">${exec.tradeoff || "no tradeoff"}</div>
        <div class="runtime-event-sub">${exec.reasoning || "No arbitration reasoning available."}</div>
      </div>
    `;

    rankedEl.innerHTML = ranked.length
      ? ranked.map(item => `
          <div class="runtime-event runtime-insight-card severity-info">
            <div class="runtime-event-main">${item.strategy} · ${item.arbitration_score}</div>
            <div class="runtime-event-sub">${item.tradeoff}</div>
          </div>
        `).join("")
      : '<div class="runtime-empty">No ranked strategies available.</div>';

  } catch (err) {
    decisionEl.innerHTML = '<div class="runtime-empty">Strategy arbitration API unavailable.</div>';
    rankedEl.innerHTML = '<div class="runtime-empty">Strategy arbitration API unavailable.</div>';
  }
}

loadStrategyArbitrationSnapshot();
setInterval(loadStrategyArbitrationSnapshot, 15000);
</script>
'''

if "loadStrategyArbitrationSnapshot" in text:
    print("strategy arbitration loader already exists")
else:
    if "</body>" not in text:
        raise SystemExit("body close tag not found")
    text = text.replace("</body>", script + "\n</body>", 1)
    path.write_text(text, encoding="utf-8")
    print("strategy arbitration loader added")
