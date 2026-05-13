class RuntimeReflectionEngine:
    def reflect(self, forecast_data, evolution_data, strategy_data, execution_plan_data):
        issues = []
        confirmations = []
        safeguards = []

        forecast_state = (forecast_data.get("summary") or {}).get("forecast_state", "unknown")
        instability = (forecast_data.get("summary") or {}).get("instability_probability", 0)

        confidence = (evolution_data.get("recommendation_confidence") or {}).get("score", 0)
        confidence_state = (evolution_data.get("recommendation_confidence") or {}).get("state", "unknown")

        best_reduction = (strategy_data.get("summary") or {}).get("estimated_best_reduction", 0)
        best_strategy = (strategy_data.get("summary") or {}).get("best_strategy", "unknown")

        high_risk_plans = (execution_plan_data.get("summary") or {}).get("high_risk_plans", 0)

        if forecast_state == "critical_watch" and confidence >= 80:
            confirmations.append("Forecast and recommendation confidence are aligned.")

        if instability >= 0.9 and best_reduction < 20:
            issues.append("Strategy reduction may be too weak for high instability.")

        if high_risk_plans > 0:
            safeguards.append("Require human approval before executing high-risk planning phases.")

        if confidence >= 90 and forecast_state != "stable":
            safeguards.append("Maintain recommendation-only mode despite high confidence.")

        if best_strategy == "Blueprint Extraction":
            confirmations.append("Blueprint extraction matches current route concentration pressure.")

        reflection_score = self._score(issues, confirmations, safeguards)

        return {
            "bounded": True,
            "mode": "self_reflection_only",
            "autonomous_apply": False,
            "summary": {
                "reflection_score": reflection_score,
                "issues": len(issues),
                "confirmations": len(confirmations),
                "safeguards": len(safeguards),
                "confidence_state": confidence_state,
                "forecast_state": forecast_state,
            },
            "issues": issues,
            "confirmations": confirmations,
            "safeguards": safeguards,
            "reflection": self._reflection_message(reflection_score, issues),
            "notes": [
                "Reflection engine reviews runtime reasoning consistency only.",
                "No autonomous execution is permitted.",
                "Human approval remains required for all structural changes."
            ],
        }

    def _score(self, issues, confirmations, safeguards):
        score = 70
        score += len(confirmations) * 10
        score += len(safeguards) * 5
        score -= len(issues) * 15
        return max(0, min(score, 100))

    def _reflection_message(self, score, issues):
        if issues:
            return "Runtime reasoning is mostly coherent but requires additional caution."
        if score >= 90:
            return "Runtime reasoning appears coherent and safety-aligned."
        return "Runtime reasoning is acceptable but should remain under review."
