from pathlib import Path
import re

class ArchitectureHotspotDetector:
    def __init__(self, root="."):
        self.root = Path(root)

    def analyze(self):
        py_files = list(self.root.rglob("*.py"))
        html_files = list(self.root.rglob("*.html"))

        ignored = {".git", "__pycache__", ".venv", "venv", "runtime_logs", "backups", "AI_SANDBOX"}
        py_files = [p for p in py_files if not any(x in p.parts for x in ignored)]
        html_files = [p for p in html_files if not any(x in p.parts for x in ignored)]

        file_scores = []
        route_density = []
        fragile_zones = []

        for path in py_files:
            if path.name.startswith("patch_"):
                continue

            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            lines = text.splitlines()
            route_count = len(re.findall(r"@\w+\.route|@app\.route", text))
            function_count = len(re.findall(r"^\s*def\s+", text, re.M))
            class_count = len(re.findall(r"^\s*class\s+", text, re.M))
            import_count = len(re.findall(r"^\s*(import|from)\s+", text, re.M))

            score = 0
            score += min(len(lines) // 80, 10)
            score += min(route_count * 2, 20)
            score += min(function_count, 15)
            score += min(import_count // 3, 10)

            risk = "low"
            if score >= 25:
                risk = "high"
            elif score >= 14:
                risk = "medium"

            item = {
                "file": str(path),
                "lines": len(lines),
                "routes": route_count,
                "functions": function_count,
                "classes": class_count,
                "imports": import_count,
                "hotspot_score": score,
                "risk": risk,
            }

            file_scores.append(item)

            if route_count:
                route_density.append(item)

            if risk in {"medium", "high"}:
                fragile_zones.append({
                    "file": str(path),
                    "risk": risk,
                    "reason": self._reason(item),
                    "recommendation": self._recommendation(item),
                })

        file_scores.sort(key=lambda x: x["hotspot_score"], reverse=True)
        route_density.sort(key=lambda x: x["routes"], reverse=True)

        return {
            "bounded": True,
            "mode": "read_only_analysis",
            "autonomous_apply": False,
            "summary": {
                "python_files_scanned": len(py_files),
                "html_files_scanned": len(html_files),
                "hotspots_found": len([x for x in file_scores if x["risk"] != "low"]),
                "high_risk_files": len([x for x in file_scores if x["risk"] == "high"]),
                "route_dense_files": len(route_density),
            },
            "top_hotspots": file_scores[:10],
            "route_density": route_density[:10],
            "fragile_zones": fragile_zones[:10],
            "notes": [
                "This engine performs read-only architecture hotspot analysis.",
                "No files are modified by this detector.",
                "Use results for human-reviewed modularization planning only."
            ],
        }

    def _reason(self, item):
        reasons = []
        if item["lines"] > 500:
            reasons.append("large file size")
        if item["routes"] > 8:
            reasons.append("high route concentration")
        if item["functions"] > 20:
            reasons.append("many functions in one file")
        if item["imports"] > 25:
            reasons.append("high dependency surface")
        return ", ".join(reasons) or "combined structural complexity"

    def _recommendation(self, item):
        if item["routes"] > 8:
            return "Consider splitting routes into blueprint/module files after human review."
        if item["lines"] > 500:
            return "Consider modularizing this file into smaller responsibility-based components."
        return "Monitor this file and review before adding more responsibilities."
