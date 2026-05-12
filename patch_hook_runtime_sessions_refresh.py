from pathlib import Path

p = Path("templates/jarvis/mobile_control_center.html")
text = p.read_text(encoding="utf-8")

if "renderRuntimeSessions(data);" not in text:
    targets = [
        "renderWorkerState(data);",
        "renderRuntimeHealth(data);",
        "renderCommandQueue(data);",
        "renderLearningMemory(data);",
    ]

    patched = False
    for target in targets:
        if target in text:
            text = text.replace(
                target,
                target + "\n    renderRuntimeSessions(data);",
                1
            )
            patched = True
            break

    if not patched:
        raise SystemExit("ERROR: no refresh render hook found")

p.write_text(text, encoding="utf-8")
print("✅ hooked renderRuntimeSessions into HUD refresh")
