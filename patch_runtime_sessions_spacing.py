from pathlib import Path

path = Path("templates/jarvis/mobile_control_center.html")
text = path.read_text(encoding="utf-8")

css = '''

body{
  padding-bottom:140px !important;
}

.runtime-sessions-wrapper{
  margin-bottom:140px !important;
}

#runtime-sessions-panel{
  position:relative;
  z-index:2;
}

.runtime-sessions-feed{
  min-height:220px;
}

'''

if "padding-bottom:140px" not in text:
    style_end = text.rfind("</style>")

    if style_end != -1:
        text = text[:style_end] + css + "\n" + text[style_end:]
    else:
        text += f"<style>{css}</style>"

path.write_text(text, encoding="utf-8")

print("✅ runtime sessions spacing fixed")
