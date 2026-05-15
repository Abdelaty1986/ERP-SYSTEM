import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_MEMORY = PROJECT_ROOT / "JARVIS_CORE" / "runtime_memory"

SAFETY_CONTRACT = {
    "bounded": True,
    "analysis_only": True,
    "execution_allowed": False,
    "apply_allowed": False,
    "autonomous_apply": False,
    "database_mutation_allowed": False,
    "deploy_allowed": False,
    "human_approval_required": True,
}

CORE_PATHS = {
    "routes": ["app.py", "views.py", "operations.py", "financial.py", "documents.py", "advanced.py"],
    "modules": ["modules"],
    "templates": ["templates"],
    "static": ["static"],
    "runtime": ["JARVIS_CORE/jarvis", "JARVIS_CORE/runtime_memory", "JARVIS_CORE/runtime_logs"],
    "database_files": ["database.db", "instance"],
    "tests": ["tests"],
}

RISK_RULES = [
    ("high", ("database.db", "migrations.py", "db.py", "deploy.sh", "Procfile", "nixpacks.toml")),
    ("high", ("modules/sales", "modules/hr", "modules/inventory", "modules/reports")),
    ("high", ("app.py",)),
    ("medium", ("templates", "static", "views.py", "operations.py", "financial.py", "documents.py", "advanced.py")),
    ("medium", ("JARVIS_CORE/jarvis/runtime", "JARVIS_CORE/jarvis/architecture")),
    ("low", ("docs", "README", "tests", "AI_TASKS")),
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _as_posix(path):
    return path.relative_to(PROJECT_ROOT).as_posix()


def _exists(path):
    return (PROJECT_ROOT / path).exists()


def _safe_read(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _write_json(path, payload):
    RUNTIME_MEMORY.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _iter_files(base, suffixes=None, limit=None):
    root = PROJECT_ROOT / base
    if not root.exists():
        return []
    files = []
    for item in root.rglob("*"):
        if not item.is_file():
            continue
        rel = _as_posix(item)
        if suffixes and item.suffix.lower() not in suffixes:
            continue
        files.append(rel)
        if limit and len(files) >= limit:
            break
    return sorted(files)


def _route_paths(py_path):
    path = PROJECT_ROOT / py_path
    text = _safe_read(path)
    if not text:
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    routes = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            call = decorator if isinstance(decorator, ast.Call) else None
            if not call:
                continue
            attr = call.func
            if not isinstance(attr, ast.Attribute) or attr.attr != "route":
                continue
            if call.args and isinstance(call.args[0], ast.Constant):
                routes.append({"route": call.args[0].value, "handler": node.name, "file": py_path})
    return routes


def _template_refs(py_path):
    text = _safe_read(PROJECT_ROOT / py_path)
    refs = sorted(set(re.findall(r"render_template\(\s*[\"']([^\"']+)[\"']", text)))
    return [{"template": ref, "exists": _exists(f"templates/{ref}")} for ref in refs]


def _imports(py_path):
    path = PROJECT_ROOT / py_path
    text = _safe_read(path)
    if not text:
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return sorted(set(imports))


def build_inventory():
    route_files = [path for path in CORE_PATHS["routes"] if _exists(path)]
    module_dirs = [p.name for p in (PROJECT_ROOT / "modules").iterdir() if p.is_dir()] if _exists("modules") else []
    template_files = _iter_files("templates", {".html"})
    static_files = _iter_files("static", {".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".ico"})
    runtime_files = _iter_files("JARVIS_CORE/jarvis", {".py"}, limit=400)
    routes = []
    template_references = []
    for file_name in route_files + _iter_files("modules", {".py"}):
        routes.extend(_route_paths(file_name))
        template_references.extend({"file": file_name, **ref} for ref in _template_refs(file_name))
    return {
        "phase": "Phase 8 - Autonomous ERP Evolution",
        "layer": "Layer 1 - ERP Module Inventory",
        "generated_at": _now(),
        "safety": SAFETY_CONTRACT,
        "state": "complete",
        "project_root": str(PROJECT_ROOT),
        "core_paths": {key: [{"path": item, "exists": _exists(item)} for item in paths] for key, paths in CORE_PATHS.items()},
        "counts": {
            "route_files": len(route_files),
            "module_directories": len(module_dirs),
            "templates": len(template_files),
            "static_assets": len(static_files),
            "runtime_python_files_sampled": len(runtime_files),
            "routes_detected": len(routes),
            "template_references_detected": len(template_references),
        },
        "modules": sorted(module_dirs),
        "route_files": route_files,
        "template_files": template_files,
        "static_files": static_files,
        "runtime_python_files": runtime_files,
        "routes": routes,
        "template_references": template_references,
    }


def classify_risk(rel_path):
    normalized = rel_path.replace("\\", "/")
    for level, needles in RISK_RULES:
        for needle in needles:
            if normalized == needle or normalized.startswith(f"{needle}/") or needle in normalized:
                return level
    if normalized.endswith(".db") or "backup" in normalized:
        return "high"
    if normalized.endswith((".py", ".html", ".css", ".js")):
        return "medium"
    return "low"


def build_risk_mapping(inventory):
    candidates = set()
    for key in ("route_files", "template_files", "static_files", "runtime_python_files"):
        candidates.update(inventory.get(key, []))
    candidates.update(f"modules/{module}" for module in inventory.get("modules", []))
    candidates.update(["database.db", "migrations.py", "db.py", "deploy.sh", "instance"])
    buckets = {"high": [], "medium": [], "low": []}
    for item in sorted(candidates):
        risk = classify_risk(item)
        buckets[risk].append(
            {
                "path": item,
                "risk": risk,
                "reason": _risk_reason(item, risk),
                "allowed_action": "analyze_only",
                "requires_human_approval": True,
            }
        )
    return {
        "phase": "Phase 8 - Autonomous ERP Evolution",
        "layer": "Layer 2 - ERP Risk Mapping",
        "generated_at": _now(),
        "safety": SAFETY_CONTRACT,
        "state": "complete",
        "risk_policy": {
            "high": "No direct mutation. Require explicit human approval, backup, tests, and rollback plan.",
            "medium": "Review dependencies first. UI-only or isolated changes require approval.",
            "low": "Documentation or test-support changes still stay bounded and reviewable.",
        },
        "summary": {key: len(value) for key, value in buckets.items()},
        "high_risk": buckets["high"],
        "medium_risk": buckets["medium"],
        "low_risk": buckets["low"],
    }


def _risk_reason(path, risk):
    if path.endswith(".db") or "database" in path or path in {"db.py", "migrations.py"}:
        return "Database schema or data surface; mutation is blocked in Phase 8."
    if path == "app.py" or path.startswith("modules/"):
        return "Route and business logic surface with broad ERP impact."
    if path.startswith("templates") or path.startswith("static"):
        return "User-facing UI surface; safe only as limited, explicit edits."
    if path.startswith("JARVIS_CORE"):
        return "Runtime governance surface; analysis-only outputs are allowed."
    return f"{risk.capitalize()} operational impact based on path classification."


def build_dependency_graph(inventory):
    route_files = inventory.get("route_files", [])
    module_py = _iter_files("modules", {".py"})
    graph = {
        "routes_to_templates": {},
        "python_imports": {},
        "static_to_templates": {},
        "runtime_memory_outputs": [
            "JARVIS_CORE/runtime_memory/erp_module_inventory.json",
            "JARVIS_CORE/runtime_memory/erp_risk_mapping.json",
            "JARVIS_CORE/runtime_memory/erp_dependency_graph.json",
            "JARVIS_CORE/runtime_memory/erp_safe_evolution_plan.json",
            "JARVIS_CORE/runtime_memory/erp_human_approval_gateway.json",
        ],
    }
    for file_name in route_files + module_py:
        refs = _template_refs(file_name)
        if refs:
            graph["routes_to_templates"][file_name] = refs
        imports = [name for name in _imports(file_name) if name.startswith(("modules", "JARVIS_CORE", "jarvis", "db", "views"))]
        if imports:
            graph["python_imports"][file_name] = imports
    for template in inventory.get("template_files", []):
        text = _safe_read(PROJECT_ROOT / template)
        refs = sorted(set(re.findall(r"(?:url_for\(\s*[\"']static[\"'].*?filename=[\"']([^\"']+)[\"']|static/([^\"' )]+))", text)))
        flat_refs = sorted({item for pair in refs for item in pair if item})
        if flat_refs:
            graph["static_to_templates"][template] = flat_refs
    return {
        "phase": "Phase 8 - Autonomous ERP Evolution",
        "layer": "Layer 3 - ERP Dependency Graph",
        "generated_at": _now(),
        "safety": SAFETY_CONTRACT,
        "state": "complete",
        "graph": graph,
        "notes": [
            "Graph is built from static AST and text analysis only.",
            "No production file, database, or deploy mutation was performed.",
        ],
    }


def build_safe_plan(inventory, risk_mapping, dependency_graph):
    high_count = risk_mapping["summary"]["high"]
    medium_count = risk_mapping["summary"]["medium"]
    return {
        "phase": "Phase 8 - Autonomous ERP Evolution",
        "layer": "Layer 4 - ERP Safe Evolution Planner",
        "generated_at": _now(),
        "safety": SAFETY_CONTRACT,
        "state": "complete",
        "plan_type": "recommendations_only",
        "execution_allowed": False,
        "recommended_sequence": [
            {
                "step": "Freeze safety contract",
                "action": "Keep apply_allowed=false and require explicit approval before any future ERP edit.",
                "risk": "low",
            },
            {
                "step": "Start with UI-only improvements",
                "action": "Target isolated templates with known route ownership and no database writes.",
                "risk": "medium",
            },
            {
                "step": "Defer business-logic refactors",
                "action": "Create a reviewed diff plan before touching app.py, db.py, migrations.py, or modules/*.",
                "risk": "high",
            },
            {
                "step": "Probe dependencies before change",
                "action": "Rebuild inventory, risk map, and dependency graph immediately before implementation.",
                "risk": "medium",
            },
            {
                "step": "Human approval gate",
                "action": "Require explicit human approval phrase and rollback plan before execution.",
                "risk": "high",
            },
        ],
        "current_surface": {
            "modules_detected": inventory["counts"]["module_directories"],
            "routes_detected": inventory["counts"]["routes_detected"],
            "templates_detected": inventory["counts"]["templates"],
            "high_risk_items": high_count,
            "medium_risk_items": medium_count,
            "dependency_edges": sum(len(v) for v in dependency_graph["graph"]["routes_to_templates"].values()),
        },
        "blocked_actions": [
            "autonomous_apply",
            "database_mutation",
            "deployment",
            "production_file_rewrite_without_approval",
        ],
    }


def build_approval_gateway():
    return {
        "phase": "Phase 8 - Autonomous ERP Evolution",
        "layer": "Layer 5 - ERP Human Approval Gateway",
        "generated_at": _now(),
        "safety": SAFETY_CONTRACT,
        "state": "complete",
        "gateway_state": "armed_for_future_review_only",
        "execution_allowed": False,
        "approval_required_for": [
            "Any write outside JARVIS_CORE/runtime_memory",
            "Any route, module, template, static, or database-affecting change",
            "Any command that mutates database, deploys, or applies patches",
        ],
        "approval_contract": {
            "required_phrase": "APPROVE_ERP_EVOLUTION",
            "requires_named_files": True,
            "requires_risk_summary": True,
            "requires_test_plan": True,
            "requires_rollback_plan": True,
            "expires_after_single_use": True,
        },
        "denied_without_approval": {
            "execution_allowed": False,
            "apply_allowed": False,
            "database_mutation_allowed": False,
            "deploy_allowed": False,
        },
    }


def run_phase8():
    inventory = build_inventory()
    _write_json(RUNTIME_MEMORY / "erp_module_inventory.json", inventory)
    risk_mapping = build_risk_mapping(inventory)
    _write_json(RUNTIME_MEMORY / "erp_risk_mapping.json", risk_mapping)
    dependency_graph = build_dependency_graph(inventory)
    _write_json(RUNTIME_MEMORY / "erp_dependency_graph.json", dependency_graph)
    safe_plan = build_safe_plan(inventory, risk_mapping, dependency_graph)
    _write_json(RUNTIME_MEMORY / "erp_safe_evolution_plan.json", safe_plan)
    approval_gateway = build_approval_gateway()
    _write_json(RUNTIME_MEMORY / "erp_human_approval_gateway.json", approval_gateway)
    return {
        "phase": "Phase 8 - Autonomous ERP Evolution",
        "generated_at": _now(),
        "safety": SAFETY_CONTRACT,
        "layers": {
            "layer_1_inventory": "complete",
            "layer_2_risk_mapping": "complete",
            "layer_3_dependency_graph": "complete",
            "layer_4_safe_evolution_planner": "complete",
            "layer_5_human_approval_gateway": "complete",
        },
        "outputs": [
            "JARVIS_CORE/runtime_memory/erp_module_inventory.json",
            "JARVIS_CORE/runtime_memory/erp_risk_mapping.json",
            "JARVIS_CORE/runtime_memory/erp_dependency_graph.json",
            "JARVIS_CORE/runtime_memory/erp_safe_evolution_plan.json",
            "JARVIS_CORE/runtime_memory/erp_human_approval_gateway.json",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(run_phase8(), ensure_ascii=False, indent=2))
