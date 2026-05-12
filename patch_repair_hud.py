from pathlib import Path

path = Path("templates/jarvis/mobile_control_center.html")
text = path.read_text(encoding="utf-8")

panel = '''
    <div class="panel" id="repair-panel">
      <div class="panel-title">حلقة الإصلاح الذاتي</div>
      <div class="panel-sub">Autonomous Repair Loop</div>
      <div class="gitbox"><div class="label">Repair Status</div><div class="value" id="repair-status">Loading...</div></div>
      <div class="gitbox"><div class="label">Auto Apply</div><div class="value" id="repair-auto-apply">--</div></div>
      <div class="gitbox"><div class="label">Finding</div><div class="value" id="repair-finding">--</div></div>
    </div>
'''

if 'id="repair-panel"' not in text:
    text = text.replace(
        '<div class="panel" id="consensus-panel">',
        panel + '\n\n    <div class="panel" id="consensus-panel">'
    )

if 'repair-status' in text and 'data.repair' in text:
    print("Repair HUD already wired")
else:
    text = text.replace(
        'const consensusDecision = document.getElementById("consensus-decision");',
        '''const repairStatus = document.getElementById("repair-status");
    const repairAutoApply = document.getElementById("repair-auto-apply");
    const repairFinding = document.getElementById("repair-finding");

    if(data.repair){
      if(repairStatus) repairStatus.textContent = data.repair.status;
      if(repairAutoApply) repairAutoApply.textContent = data.repair.auto_apply ? "YES" : "NO";
      if(repairFinding && data.repair.findings && data.repair.findings[0]){
        repairFinding.textContent = data.repair.findings[0].category;
      }
    }

    const consensusDecision = document.getElementById("consensus-decision");'''
    )

path.write_text(text, encoding="utf-8")
print("Repair HUD injected")
