class CognitiveDecisionEngine:
    def decide(self, reflection_data, strategy_data, execution_plan_data):
        reflection_score = (reflection_data.get("summary") or {}).get("reflection_score", 0)
        safeguards = (reflection_data.get("summary") or {}).get("safeguards", 0)
        issues = (reflection_data.get("summary") or {}).get("issues", 0)

        strategies = strategy_data.get("strategies", []) if isinstance(strategy_data, dict) else []
        plans = execution_plan_data.get("execution_plans", []) if isinstance(execution_plan_data, dict) else []

        decisions = []
        for strategy in strategies:
            matching_plan = self._find_plan(strategy, plans)
            score = self._decision_score(strategy, matching_plan, reflection_score, safeguards, issues)

            decisions.append({
                "strategy": strategy.get("name"),
                "target": strategy.get("target"),
                "decision_score": score,
                "risk": strategy.get("risk"),
                "estimated_reduction": strategy.get("estimated_risk_reduction"),
                "decision": self._decision_state(score, strategy, issues),
                "reason": self._reason(strategy, score, reflection_score, matching_plan),
                "requires_human_review": True,
                "bounded": True,
                "mode": "decision_support_only",
                "autonomous_apply": False,
            })

        decisions.sort(key=lambda x: x["decision_score"], reverse=True)
        best = decisions[0] if decisions else None

        return {
            "bounded": True,
            "mode": "decision_support_only",
            "autonomous_apply": False,
            "summary": {
                "decisions_generated": len(decisions),
                "best_strategy": best.get("strategy") if best else None,
                "best_score": best.get("decision_score") if best else 0,
                "human_review_required": True,
            },
            "best_decision": best,
            "decisions": decisions,
            "notes": [
                "This layer supports engineering decisions only.",
                "It does not execute or modify project files.",
                "Human approval is mandatory for any future implementation."
            ],
        }

    def _find_plan(self, strategy, plans):
        name = strategy.get("name")
        for plan in plans:
            if plan.get("strategy") == name:
                return plan
        return {}

    def _decision_score(self, strategy, plan, reflection_score, safeguards, issues):
        score = 0
        score += int(strategy.get("estimated_risk_reduction", 0) or 0)
        score += min(reflection_score // 2, 50)
        score += min(len(plan.get("rollback_points", []) or []) * 3, 15)
        score += min(len(plan.get("validation_gates", []) or []) * 2, 10)
        score += min(safeguards * 3, 10)
        score -= issues * 20

        risk = strategy.get("risk")
        if risk == "low":
            score += 8
        elif risk == "low_medium":
            score += 4
        elif risk == "medium":
            score -= 2

        return max(0, min(score, 100))

    def _decision_state(self, score, strategy, issues):
        if issues > 0:
            return "hold_for_review"
        if score >= 85:
            return "recommended_for_planning"
        if score >= 65:
            return "acceptable_with_review"
        return "defer"

    def _reason(self, strategy, score, reflection_score, plan):
        return (
            f"{strategy.get('name')} scored {score} based on "
            f"estimated reduction {strategy.get('estimated_risk_reduction')}, "
            f"reflection score {reflection_score}, "
            f"{len(plan.get('validation_gates', []) or [])} validation gates, "
            f"and {len(plan.get('rollback_points', []) or [])} rollback points."
        )
