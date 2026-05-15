import json
import re
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_MEMORY = PROJECT_ROOT / "JARVIS_CORE" / "runtime_memory"
APP_FILE = PROJECT_ROOT / "app.py"


def _safe_load_json(name):
    path = RUNTIME_MEMORY / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _route_counts():
    try:
        app_text = APP_FILE.read_text(encoding="utf-8")
    except Exception:
        return {"total_routes": 0, "erp_routes": 0, "jarvis_routes": 0}

    routes = re.findall(r'@app\.route\("([^"]+)"', app_text)
    jarvis_routes = [route for route in routes if route.startswith("/jarvis")]
    erp_routes = [route for route in routes if not route.startswith("/jarvis")]
    return {
        "total_routes": len(routes),
        "erp_routes": len(erp_routes),
        "jarvis_routes": len(jarvis_routes),
    }


def build_erp_provider_status():
    inventory = _safe_load_json("erp_module_inventory.json")
    risk = _safe_load_json("erp_risk_mapping.json")
    route_counts = _route_counts()
    status = {
        "provider": "erp",
        "role": "connected_module_provider",
        "integration_mode": "read_only_status_only",
        "state": "available",
        "bounded": True,
        "database_mutation": False,
        "accounting_data_mutation": False,
        "deploy": False,
        "destructive_execution": False,
        "autonomous_apply": False,
        "human_approval_required": True,
        "governance_gates_preserved": True,
        "project_root_present": PROJECT_ROOT.exists(),
        "app_file_present": APP_FILE.exists(),
        "runtime_memory_readable": RUNTIME_MEMORY.exists(),
        "route_counts": route_counts,
        "inventory_available": bool(inventory),
        "risk_mapping_available": bool(risk),
        "checked_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    return status
