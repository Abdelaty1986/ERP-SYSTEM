import json

from jarvis.runtime.provider_trust_report import build_report as build_trust_report


class AdaptiveProviderRanking:
    """
    Adaptive provider ranking engine.

    يعتمد على:
    - historical trust score
    - success/failure history
    - last recovery state
    - bounded scoring only
    """

    def __init__(self):
        self.runtime = "adaptive_provider_ranking"
        self.bounded = True
        self.autonomous_apply = False

    def _state_bonus(self, state):
        bonuses = {
            "healthy": 0.35,
            "rate_limited": -0.45,
            "missing_credentials": -0.35,
            "model_unavailable": -0.25,
            "degraded": -0.15,
            "unavailable": -0.30,
        }

        return bonuses.get(state, -0.20)

    def rank(self):
        trust_report = build_trust_report()
        providers = trust_report.get("providers", {})

        rankings = []

        for name, data in providers.items():
            trust_score = data.get("trust_score", 0)
            success_count = data.get("success_count", 0)
            failure_count = data.get("failure_count", 0)
            last_state = data.get("last_state", "unknown")

            total = success_count + failure_count

            success_ratio = (
                success_count / total
                if total > 0
                else 0
            )

            final_score = round(
                (
                    trust_score * 0.6
                    + success_ratio * 0.25
                    + self._state_bonus(last_state) * 0.15
                ),
                3
            )

            rankings.append({
                "provider": name,
                "trust_score": trust_score,
                "success_ratio": round(success_ratio, 3),
                "last_state": last_state,
                "final_score": final_score,
                "recommended": False,
            })

        rankings.sort(
            key=lambda item: item["final_score"],
            reverse=True,
        )

        if rankings:
            rankings[0]["recommended"] = True

        return {
            "runtime": self.runtime,
            "bounded": self.bounded,
            "autonomous_apply": self.autonomous_apply,
            "provider_count": len(rankings),
            "recommended_provider": (
                rankings[0]["provider"]
                if rankings
                else None
            ),
            "rankings": rankings,
        }


if __name__ == "__main__":
    result = AdaptiveProviderRanking().rank()
    print(json.dumps(result, ensure_ascii=False, indent=2))
