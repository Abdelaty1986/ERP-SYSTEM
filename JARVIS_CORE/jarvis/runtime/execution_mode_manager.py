import json
from pathlib import Path

MODE_FILE = Path("JARVIS_CORE/runtime_memory/runtime_execution_mode.json")
ALLOWED_MODES = {"simulation_only", "controlled_real_execution", "supervised_real_execution"}

def read_mode() -> dict:
    MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not MODE_FILE.exists():
        default = {"mode": "controlled_real_execution", "updated_at": None}
        MODE_FILE.write_text(json.dumps(default, indent=2), encoding="utf-8")
        return default
    try:
        return json.loads(MODE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"mode": "controlled_real_execution", "updated_at": None}

def write_mode(mode: str, confirm: str = "") -> dict:
    if mode not in ALLOWED_MODES:
        return {"ok": False, "error": f"Invalid mode: {mode}. Allowed: {', '.join(sorted(ALLOWED_MODES))}"}
    if mode == "supervised_real_execution" and confirm != "ENABLE_SUPERVISED_REAL_EXECUTION":
        return {"ok": False, "error": "Confirmation required. Set confirm=ENABLE_SUPERVISED_REAL_EXECUTION"}
    if mode == "controlled_real_execution" and confirm != "ENABLE_CONTROLLED_REAL_EXECUTION":
        return {"ok": False, "error": "Confirmation required. Set confirm=ENABLE_CONTROLLED_REAL_EXECUTION"}
    from datetime import datetime
    payload = {"mode": mode, "updated_at": datetime.utcnow().isoformat() + "Z"}
    MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
    MODE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"ok": True, **payload}
