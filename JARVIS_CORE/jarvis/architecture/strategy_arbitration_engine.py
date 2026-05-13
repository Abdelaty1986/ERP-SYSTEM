class StrategyArbitrationEngine:
    def arbitrate(self, decision_data):
        decisions = decision_data.get("decisions", []) if isinstance(decision_data, dict) else []

        ranked = []
        for item in decisions:
            arbitration_score = self._score(item)

            ranked.append({
                "strategy": item.get("strategy"),
                "target": item.get("target"),
                "decision_score": item.get("decision_score"),
                "arbitration_score": arbitration_score,
                "risk": item.get("risk"),
                "estimated_reduction": item.get("estimated_reduction"),
                "tradeoff": self._tradeoff(item),
                "execution_preference": self._preference(arbitration_score),
                "reasoning": self._reasoning(item, arbitration_score),
                "bounded": True,
                "mode": "executive_arbitration_only",
                "autonomous_apply": False,
            })

        ranked.sort(key=lambda x: x["arbitration_score"], reverse=True)
        best = ranked[0] if ranked else None

        return {
            "bounded": True,
            "mode": "executive_arbitration_only",
            "autonomous_apply": False,
            "summary": {
                "strategies_ranked": len(ranked),
                "best_strategy": best.get("strategy") if best else None,
                "best_arbitration_score": best.get("arbitration_score") if best else 0,
            },
            "executive_decision": best,
            "ranked_strategies": ranked,
            "notes": [
                "Arbitration balances reduction, risk, and execution stability.",
                "No autonomous execution is permitted.",
                "Human review remains mandatory."
            ],
        }

    def _score(self, item):
        base = int(item.get("decision_score", 0) or 0)

        reduction = int(item.get("estimated_reduction", 0) or 0)
        risk = item.get("risk")

        if risk == "low":
            base += 12
        elif risk == "low_medium":
            base += 6
        elif risk == "medium":
            base -= 5

        base += reduction // 2

        return max(0, min(base, 100))

    def _tradeoff(self, item):
        reduction = int(item.get("estimated_reduction", 0) or 0)
        risk = item.get("risk")

        if reduction >= 30 and risk == "medium":
            return "high_reward_balanced_risk"

        if reduction >= 20 and risk in {"low", "low_medium"}:
            return "safe_balanced_progress"

        return "slow_safe_stabilization"

    def _preference(self, score):
        if score >= 90:
            return "primary_candidate"
        if score >= 75:
            return "secondary_candidate"
        return "reserve_candidate"

    def _reasoning(self, item, score):
        return (
            f"{item.get('strategy')} received arbitration score {score} "
            f"with risk {item.get('risk')} and reduction "
            f"{item.get('estimated_reduction')}."
        )
