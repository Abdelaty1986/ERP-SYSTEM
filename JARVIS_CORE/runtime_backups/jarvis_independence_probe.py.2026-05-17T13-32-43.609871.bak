import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
APP_FILE = ROOT / "app.py"
API_FILE = ROOT / "jarvis_app" / "api.py"
RUNTIME_MEMORY = ROOT / "JARVIS_CORE" / "runtime_memory"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jarvis_server import create_app
from providers.erp_provider import build_erp_provider_status


REQUIRED_FILES = [
    "jarvis_server.py",
    "jarvis_app/__init__.py",
    "jarvis_app/api.py",
    "jarvis_mobile/__init__.py",
    "jarvis_runtime/__init__.py",
    "jarvis_memory/README.md",
    "jarvis_logs/README.md",
    "jarvis_reports/README.md",
    "providers/__init__.py",
    "providers/erp_provider.py",
    "JARVIS_CORE/runtime_memory/jarvis_independence_inventory.json",
    "JARVIS_CORE/runtime_memory/jarvis_independence_report.json",
    "JARVIS_CORE/runtime_memory/jarvis_route_compatibility_report.json",
    "JARVIS_CORE/runtime_memory/erp_provider_status.json",
]

INDEPENDENT_ROUTES = [
    "/jarvis/api/status",
    "/jarvis/api/runtime/status",
    "/jarvis/api/agents/status",
    "/jarvis/api/mobile/status",
    "/jarvis/api/voice/status",
    "/jarvis/api/providers/erp/status",
]

LEGACY_ROUTES = [
    "/jarvis/mobile",
    "/jarvis/mobile/api/status",
    "/jarvis/mobile/api/voice/command",
    "/jarvis/mobile/api/app/status",
    "/jarvis/mobile/api/runtime/control/status",
]


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def route_exists_in_source(route):
    text = APP_FILE.read_text(encoding="utf-8") + "\n" + API_FILE.read_text(encoding="utf-8")
    return route in text


def validate_independent_routes():
    app = create_app()
    client = app.test_client()
    results = {}
    for route in INDEPENDENT_ROUTES:
        response = client.get(route)
        results[route] = response.status_code == 200 and response.is_json
    return results


def main():
    app_text = APP_FILE.read_text(encoding="utf-8")
    route_results = validate_independent_routes()
    provider_status = build_erp_provider_status()
    inventory = load_json(RUNTIME_MEMORY / "jarvis_independence_inventory.json")
    report = load_json(RUNTIME_MEMORY / "jarvis_independence_report.json")
    compatibility = load_json(RUNTIME_MEMORY / "jarvis_route_compatibility_report.json")

    checks = {
        "required_files_exist": all((ROOT / name).exists() for name in REQUIRED_FILES),
        "app_registers_independent_blueprint": "create_jarvis_blueprint" in app_text,
        "independent_routes_registered_in_source": all(route_exists_in_source(route) for route in INDEPENDENT_ROUTES),
        "independent_routes_respond": all(route_results.values()),
        "legacy_mobile_routes_preserved": all(route_exists_in_source(route) for route in LEGACY_ROUTES),
        "erp_provider_read_only": provider_status.get("integration_mode") == "read_only_status_only",
        "erp_provider_no_mutation": provider_status.get("database_mutation") is False,
        "runtime_memory_readable": RUNTIME_MEMORY.exists(),
        "inventory_bounded": inventory.get("bounded") is True,
        "report_governance_preserved": report.get("safety", {}).get("governance_gates_preserved") is True,
        "compatibility_state_ok": compatibility.get("state") == "compatible",
        "no_file_deletion": report.get("safety", {}).get("file_deletion") is False,
        "no_dangerous_migration": report.get("safety", {}).get("dangerous_migration") is False,
        "app_has_erp_routes": re.search(r'@app\.route\("/accounts"', app_text) is not None,
    }

    result = {
        "phase": "Phase 20 - JARVIS Independence Extraction Layer",
        "state": "operational" if all(checks.values()) else "needs_review",
        "ok": all(checks.values()),
        "checks": checks,
        "independent_route_results": route_results,
        "erp_provider_status": provider_status,
        "safety": {
            "bounded": True,
            "autonomous_apply": False,
            "deploy": False,
            "destructive_execution": False,
            "database_mutation": False,
            "file_deletion": False,
            "dangerous_migration": False,
            "governance_gates_preserved": True,
        },
    }
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
