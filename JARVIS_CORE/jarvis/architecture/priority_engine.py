class ArchitecturePriorityEngine:
    def build_priorities(self, hotspot_data):
        hotspots = hotspot_data.get("top_hotspots", []) if isinstance(hotspot_data, dict) else []

        priorities = []
        for item in hotspots:
            impact = self._impact_score(item)
            urgency = self._urgency_score(item)
            priority_score = min(100, impact + urgency)

            level = "low"
            if priority_score >= 75:
                level = "critical"
            elif priority_score >= 55:
                level = "high"
            elif priority_score >= 35:
                level = "medium"

            priorities.append({
                "file": item.get("file"),
                "risk": item.get("risk", "unknown"),
                "hotspot_score": item.get("hotspot_score", 0),
                "impact_score": impact,
                "urgency_score": urgency,
                "priority_score": priority_score,
                "priority": level,
                "reason": self._reason(item, impact, urgency),
                "recommended_action": self._action(item),
                "bounded": True,
                "mode": "recommendation_only",
                "autonomous_apply": False,
            })

        priorities.sort(key=lambda x: x["priority_score"], reverse=True)

        return {
            "bounded": True,
            "mode": "recommendation_only",
            "autonomous_apply": False,
            "summary": {
                "priorities_generated": len(priorities),
                "critical": len([x for x in priorities if x["priority"] == "critical"]),
                "high": len([x for x in priorities if x["priority"] == "high"]),
                "medium": len([x for x in priorities if x["priority"] == "medium"]),
                "low": len([x for x in priorities if x["priority"] == "low"]),
            },
            "priorities": priorities[:10],
            "notes": [
                "Architecture priorities are generated from hotspot signals.",
                "This engine does not modify project files.",
                "All actions are advisory and require human review."
            ],
        }

    def _impact_score(self, item):
        routes = int(item.get("routes", 0) or 0)
        funcs = int(item.get("functions", 0) or 0)
        lines = int(item.get("lines", 0) or 0)
        imports = int(item.get("imports", 0) or 0)

        score = 0
        score += min(routes, 40)
        score += min(funcs // 3, 25)
        score += min(lines // 300, 20)
        score += min(imports // 5, 15)
        return min(score, 60)

    def _urgency_score(self, item):
        risk = item.get("risk", "low")
        hotspot = int(item.get("hotspot_score", 0) or 0)

        score = 0
        if risk == "high":
            score += 25
        elif risk == "medium":
            score += 15
        else:
            score += 5

        score += min(hotspot // 2, 25)
        return min(score, 40)

    def _reason(self, item, impact, urgency):
        parts = []
        if item.get("routes", 0) > 20:
            parts.append("heavy route concentration")
        if item.get("functions", 0) > 40:
            parts.append("large function surface")
        if item.get("lines", 0) > 1000:
            parts.append("large file size")
        if item.get("imports", 0) > 30:
            parts.append("wide dependency surface")

        base = ", ".join(parts) or "structural complexity signals"
        return f"{base}; impact={impact}, urgency={urgency}"

    def _action(self, item):
        if item.get("routes", 0) > 20:
            return "Plan route extraction into domain blueprints after review."
        if item.get("functions", 0) > 40:
            return "Plan function grouping into service modules after review."
        if item.get("lines", 0) > 1000:
            return "Plan file modularization by responsibility after review."
        return "Monitor and avoid adding more responsibilities."
