import json
import re
from pathlib import Path
from datetime import datetime


class ERPProjectIntelligence:
    def __init__(self, root="."):
        self.root = Path(root)
        self.app_path = self.root / "app.py"
        self.templates_path = self.root / "templates"
        self.static_path = self.root / "static"
        self.modules_path = self.root / "modules"

    def _safe_list_files(self, path, suffixes=None, limit=300):
        if not path.exists():
            return []

        files = []
        for item in path.rglob("*"):
            if not item.is_file():
                continue
            rel = str(item.relative_to(self.root))
            if suffixes and item.suffix.lower() not in suffixes:
                continue
            files.append(rel)
            if len(files) >= limit:
                break

        return sorted(files)

    def _extract_routes(self):
        if not self.app_path.exists():
            return []

        text = self.app_path.read_text(encoding="utf-8", errors="ignore")
        pattern = re.compile(r'@app\.route\(["\']([^"\']+)["\'](?:,\s*methods=([^\)]*))?\)')
        routes = []

        for match in pattern.finditer(text):
            route = match.group(1)
            methods_raw = match.group(2) or ""
            methods = re.findall(r'["\']([A-Z]+)["\']', methods_raw) or ["GET"]

            routes.append({
                "path": route,
                "methods": methods,
                "category": self._route_category(route),
            })

        return routes

    def _route_category(self, route):
        if route.startswith("/jarvis"):
            return "jarvis"
        if "sales" in route:
            return "sales"
        if "purchase" in route or "supplier" in route:
            return "purchases"
        if "customer" in route:
            return "customers"
        if "inventory" in route or "stock" in route:
            return "inventory"
        if "report" in route:
            return "reports"
        if "hr" in route:
            return "hr"
        return "general"

    def build_snapshot(self):
        routes = self._extract_routes()
        templates = self._safe_list_files(self.templates_path, {".html"})
        static_files = self._safe_list_files(self.static_path, {".css", ".js"})
        modules = self._safe_list_files(self.modules_path, {".py"})

        categories = {}
        for route in routes:
            categories[route["category"]] = categories.get(route["category"], 0) + 1

        return {
            "available": True,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "summary": {
                "route_count": len(routes),
                "template_count": len(templates),
                "static_file_count": len(static_files),
                "module_count": len(modules),
                "route_categories": categories,
            },
            "routes_sample": routes[:30],
            "templates_sample": templates[:30],
            "static_sample": static_files[:30],
            "modules_sample": modules[:30],
            "safe_mode": True,
            "bounded": True,
            "autonomy": "observation_only",
        }


def build_erp_project_snapshot():
    return ERPProjectIntelligence().build_snapshot()
