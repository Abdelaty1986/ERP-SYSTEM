from pathlib import Path

class DependencyReasoningEngine:
    def __init__(self, root="."):
        self.root = Path(root)

    def analyze(self, priority_data):
        priorities = priority_data.get("priorities", []) if isinstance(priority_data, dict) else []

        reasoning = []
        for item in priorities:
            file_path = item.get("file", "")
            domain = self._infer_domain(file_path)

            affected = self._affected_components(domain, file_path)
            cascade_risk = self._cascade_risk(item, affected)
            sequence = self._safe_sequence(domain, file_path, item)

            reasoning.append({
                "file": file_path,
                "domain": domain,
                "priority": item.get("priority"),
                "priority_score": item.get("priority_score"),
                "affected_components": affected,
                "cascade_risk": cascade_risk,
                "safe_sequence": sequence,
                "reasoning": self._reasoning_text(domain, cascade_risk, affected),
                "bounded": True,
                "mode": "recommendation_only",
                "autonomous_apply": False,
            })

        return {
            "bounded": True,
            "mode": "recommendation_only",
            "autonomous_apply": False,
            "summary": {
                "reasoning_items": len(reasoning),
                "high_cascade": len([x for x in reasoning if x["cascade_risk"] == "high"]),
                "medium_cascade": len([x for x in reasoning if x["cascade_risk"] == "medium"]),
                "low_cascade": len([x for x in reasoning if x["cascade_risk"] == "low"]),
            },
            "dependency_reasoning": reasoning[:10],
            "notes": [
                "Dependency reasoning is advisory only.",
                "No project files are modified.",
                "Safe sequences require human review before implementation."
            ],
        }

    def _infer_domain(self, file_path):
        path = str(file_path).replace("\\", "/").lower()

        known = [
            "hr", "sales", "inventory", "reports", "accounting",
            "treasury", "purchase", "auth", "users", "settings",
            "dashboard", "maintenance"
        ]

        for domain in known:
            if f"/{domain}/" in path or path.startswith(f"{domain}/") or f"{domain}_" in path:
                return domain

        if path == "app.py":
            return "core_app"

        if "migration" in path:
            return "migrations"

        if "test" in path:
            return "testing"

        return "general"

    def _affected_components(self, domain, file_path):
        components = []

        if domain == "core_app":
            components.extend([
                "global Flask routes",
                "registered blueprints",
                "shared middleware",
                "templates/*",
                "modules/*",
                "runtime endpoints"
            ])
        else:
            module_dir = self.root / "modules" / domain
            template_dir = self.root / "templates" / domain

            if module_dir.exists():
                components.append(f"modules/{domain}/*")
            if template_dir.exists():
                components.append(f"templates/{domain}/*")

            components.append(f"{domain} routes/services")
            components.append(f"{domain} templates/views")

        if "reports" in str(file_path).lower():
            components.append("financial/reporting outputs")
        if "hr" in str(file_path).lower():
            components.append("employee/payroll workflows")
        if "sales" in str(file_path).lower():
            components.append("sales/invoice workflows")

        return list(dict.fromkeys(components))

    def _cascade_risk(self, item, affected):
        score = int(item.get("priority_score", 0) or 0)
        file_path = str(item.get("file", ""))

        if file_path == "app.py" or score >= 85 or len(affected) >= 5:
            return "high"
        if score >= 55 or len(affected) >= 3:
            return "medium"
        return "low"

    def _safe_sequence(self, domain, file_path, item):
        if domain == "core_app":
            return [
                "Map routes by domain before extraction.",
                "Extract one low-risk route group first.",
                "Register blueprint without changing behavior.",
                "Run py_compile and manual route smoke test.",
                "Repeat extraction incrementally after review."
            ]

        if item.get("priority") in {"critical", "high"}:
            return [
                f"Map current {domain} functions and templates.",
                f"Group {domain} responsibilities by workflow.",
                "Extract pure helper/service logic first.",
                "Keep routes/views behavior unchanged.",
                "Run compile and endpoint smoke tests."
            ]

        return [
            "Monitor file growth.",
            "Avoid adding unrelated responsibilities.",
            "Refactor only after repeated hotspot signals."
        ]

    def _reasoning_text(self, domain, cascade_risk, affected):
        return (
            f"Domain '{domain}' has {cascade_risk} cascade risk because "
            f"{len(affected)} related component group(s) may be affected."
        )
