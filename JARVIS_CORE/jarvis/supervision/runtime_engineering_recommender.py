from datetime import datetime

from jarvis.supervision.runtime_supervision_engine import build_runtime_supervision_snapshot
from jarvis.supervision.structural_trend_forecaster import build_structural_trend_forecast


class RuntimeEngineeringRecommender:
    def __init__(self):
        self.supervision = build_runtime_supervision_snapshot()
        self.trends = build_structural_trend_forecast()

    def _recommend_for_domain(self, finding):
        domain = finding.get("domain", "unknown")
        severity = finding.get("severity", "unknown")
        templates = finding.get("templates", 0)
        modules = finding.get("modules", 0)
        risk_score = finding.get("risk_score", 0)

        if severity == "warning" and templates > 0 and modules == 0:
            return {
                "domain": domain,
                "type": "modularization",
                "priority": "high",
                "risk_score": risk_score,
                "recommendation": f"Create or connect a module ownership layer for {domain} templates.",
                "reason": f"{domain} has {templates} template(s) but no detected module ownership.",
                "safe_mode": True,
                "action_mode": "recommendation_only",
            }

        if severity == "watch":
            return {
                "domain": domain,
                "type": "domain-balancing",
                "priority": "medium",
                "risk_score": risk_score,
                "recommendation": f"Review {domain} for structural imbalance and possible decomposition.",
                "reason": f"{domain} has {templates} template(s) and {modules} module(s), indicating possible imbalance.",
                "safe_mode": True,
                "action_mode": "recommendation_only",
            }

        return {
            "domain": domain,
            "type": "maintenance",
            "priority": "low",
            "risk_score": risk_score,
            "recommendation": f"Keep monitoring {domain} as part of regular architecture supervision.",
            "reason": f"{domain} appears structurally stable in the current snapshot.",
            "safe_mode": True,
            "action_mode": "recommendation_only",
        }

    def build_recommendations(self):
        findings = self.supervision.get("domain_findings", [])
        recommendations = [self._recommend_for_domain(item) for item in findings]

        priority_order = {"high": 3, "medium": 2, "low": 1}
        recommendations.sort(
            key=lambda item: (priority_order.get(item["priority"], 0), item.get("risk_score", 0)),
            reverse=True,
        )

        high_count = len([x for x in recommendations if x["priority"] == "high"])
        medium_count = len([x for x in recommendations if x["priority"] == "medium"])
        low_count = len([x for x in recommendations if x["priority"] == "low"])

        trend_state = self.trends.get("forecast_state", "unknown")
        trend_score = self.trends.get("forecast_score", 0)

        strategic_notes = []

        if high_count:
            strategic_notes.append("High-priority modularization recommendations detected.")
        if medium_count:
            strategic_notes.append("Medium-priority domain balancing recommendations detected.")
        if trend_score > 0:
            strategic_notes.append(f"Structural trend forecast is {trend_state} with score {trend_score}.")
        if not strategic_notes:
            strategic_notes.append("Architecture recommendations are currently stable and low risk.")

        return {
            "available": True,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "summary": {
                "recommendation_count": len(recommendations),
                "high_priority": high_count,
                "medium_priority": medium_count,
                "low_priority": low_count,
                "trend_state": trend_state,
                "trend_score": trend_score,
            },
            "recommendations": recommendations[:20],
            "strategic_notes": strategic_notes,
            "safe_mode": True,
            "bounded": True,
            "autonomy": "recommendation_only",
        }


def build_engineering_recommendations():
    return RuntimeEngineeringRecommender().build_recommendations()
