class MultiAgentDeliberationEngine:
    def deliberate(self, reflection_data, decision_data, arbitration_data):
        reflection_summary = reflection_data.get("summary", {})
        decisions = decision_data.get("decisions", [])
        ranked = arbitration_data.get("ranked_strategies", [])

        agreements = []
        tensions = []
        recommendations = []

        reflection_score = reflection_summary.get("reflection_score", 0)

        for item in ranked[:3]:
            strategy = item.get("strategy")
            risk = item.get("risk")
            reduction = item.get("estimated_reduction", 0)

            if reduction >= 20:
                agreements.append(
                    f"{strategy} provides meaningful architectural reduction."
                )

            if risk in {"medium", "high"}:
                tensions.append(
                    f"{strategy} carries elevated execution sensitivity."
                )

            recommendations.append({
                "strategy": strategy,
                "consensus": self._consensus_level(
                    reflection_score,
                    reduction,
                    risk
                ),
                "recommended": reduction >= 20,
                "reasoning": (
                    f"{strategy} evaluated with reduction={reduction} "
                    f"and risk={risk}."
                ),
            })

        executive = recommendations[0] if recommendations else {}

        return {
            "bounded": True,
            "mode": "multi_agent_deliberation_only",
            "autonomous_apply": False,
            "summary": {
                "agreements": len(agreements),
                "tensions": len(tensions),
                "recommendations": len(recommendations),
                "consensus_state": executive.get("consensus", "unknown"),
            },
            "agreements": agreements,
            "tensions": tensions,
            "recommendations": recommendations,
            "executive_consensus": executive,
            "notes": [
                "Deliberation layer compares runtime reasoning outputs.",
                "No autonomous execution is allowed.",
                "Human review remains mandatory."
            ],
        }

    def _consensus_level(self, reflection_score, reduction, risk):
        if reflection_score >= 90 and reduction >= 20 and risk != "high":
            return "strong_consensus"

        if reduction >= 12:
            return "moderate_consensus"

        return "weak_consensus"
