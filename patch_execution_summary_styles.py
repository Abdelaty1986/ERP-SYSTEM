from pathlib import Path

p = Path("templates/jarvis/mobile_control_center.html")
text = p.read_text(encoding="utf-8")

styles = '''
.mini-grid{
  display:grid;
  grid-template-columns:repeat(3,1fr);
  gap:12px;
  margin-top:14px;
}

.mini-card{
  border:1px solid rgba(0,255,255,.18);
  border-radius:18px;
  padding:14px 10px;
  text-align:center;
  background:rgba(0,20,40,.45);
  box-shadow:0 0 12px rgba(0,255,255,.08);
}

.mini-card div{
  font-size:26px;
  font-weight:700;
  color:#7eeeff;
}

.mini-card span{
  display:block;
  margin-top:6px;
  font-size:12px;
  opacity:.8;
}
'''

if ".mini-grid{" not in text:
    marker = "</style>"
    idx = text.find(marker)

    if idx == -1:
        raise SystemExit("ERROR: style block not found")

    text = text[:idx] + styles + "\n" + text[idx:]

p.write_text(text, encoding="utf-8")
print("✅ execution summary styles added")
