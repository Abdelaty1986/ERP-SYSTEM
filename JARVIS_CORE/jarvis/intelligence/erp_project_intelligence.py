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

    def _domain_from_file(self, file_path):
        lowered = file_path.lower()

        if "sales" in lowered:
            return "sales"
        if "purchase" in lowered or "supplier" in lowered:
            return "purchases"
        if "customer" in lowered or "party" in lowered:
            return "customers"
        if "inventory" in lowered or "stock" in lowered or "product" in lowered:
            return "inventory"
        if "report" in lowered:
            return "reports"
        if "hr" in lowered or "employee" in lowered:
            return "hr"
        if "jarvis" in lowered:
            return "jarvis"
        if "account" in lowered or "ledger" in lowered or "journal" in lowered:
            return "accounting"
        return "general"

    def _map_domains(self, templates, modules):
        domains = {}

        for file_path in templates:
            domain = self._domain_from_file(file_path)
            domains.setdefault(domain, {"templates": 0, "modules": 0})
            domains[domain]["templates"] += 1

        for file_path in modules:
            domain = self._domain_from_file(file_path)
            domains.setdefault(domain, {"templates": 0, "modules": 0})
            domains[domain]["modules"] += 1

        return domains

    def _build_relationships(self, routes, templates, modules):
        domain_map = self._map_domains(templates, modules)

        route_domain_links = []
        for route in routes[:80]:
            category = route.get("category", "general")
            domain_state = domain_map.get(category, {"templates": 0, "modules": 0})
            route_domain_links.append({
                "route": route.get("path"),
                "category": category,
                "template_candidates": domain_state.get("templates", 0),
                "module_candidates": domain_state.get("modules", 0),
            })

        module_domains = {}
        for module in modules:
            domain = self._domain_from_file(module)
            module_domains.setdefault(domain, []).append(module)

        template_domains = {}
        for template in templates:
            domain = self._domain_from_file(template)
            template_domains.setdefault(domain, []).append(template)

        architecture_notes = []
        for domain, counts in sorted(domain_map.items()):
            if counts["templates"] and counts["modules"]:
                architecture_notes.append(
                    f"{domain} has both templates and modules, suggesting a structured business domain."
                )
            elif counts["templates"] and not counts["modules"]:
                architecture_notes.append(
                    f"{domain} has templates without clear module ownership."
                )
            elif counts["modules"] and not counts["templates"]:
                architecture_notes.append(
                    f"{domain} has modules without obvious template presence."
                )

        return {
            "domain_map": domain_map,
            "route_domain_links_sample": route_domain_links[:30],
            "module_domains_sample": {k: v[:10] for k, v in module_domains.items()},
            "template_domains_sample": {k: v[:10] for k, v in template_domains.items()},
            "architecture_notes": architecture_notes[:20],
        }

    def build_snapshot(self):
        routes = self._extract_routes()
        templates = self._safe_list_files(self.templates_path, {".html"})
        static_files = self._safe_list_files(self.static_path, {".css", ".js"})
        modules = self._safe_list_files(self.modules_path, {".py"})

        categories = {}
        for route in routes:
            categories[route["category"]] = categories.get(route["category"], 0) + 1

        relationships = self._build_relationships(routes, templates, modules)

        return {
            "available": True,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "summary": {
                "route_count": len(routes),
                "template_count": len(templates),
                "static_file_count": len(static_files),
                "module_count": len(modules),
                "route_categories": categories,
                "relationship_domains": len(relationships.get("domain_map", {})),
            },
            "routes_sample": routes[:30],
            "templates_sample": templates[:30],
            "static_sample": static_files[:30],
            "modules_sample": modules[:30],
            "relationships": relationships,
            "safe_mode": True,
            "bounded": True,
            "autonomy": "observation_only",
        }


def build_erp_project_snapshot():
    return ERPProjectIntelligence().build_snapshot()
