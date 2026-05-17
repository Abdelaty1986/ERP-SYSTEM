import json
from datetime import datetime, timezone
from typing import Dict, Any

from jarvis.runtime.provider_optimizer import ProviderOptimizer
from jarvis.runtime.provider_forecast import ProviderForecast
from jarvis.runtime.provider_strategy_memory import ProviderStrategyMemory


class ProviderArbitration:
    def __init__(self):
        self.optimizer = ProviderOptimizer()
        self.forecast = ProviderForecast()
        self.strategy_memory = ProviderStrategyMemory()

    def _strategy_bonus(self, name: str) -> int:
        summary = self.strategy_memory.summary()
        stats = summary.get("providers", {}).get(name, {})

        attempts = int(stats.get("attempts", 0))
        successes = int(stats.get("successes", 0))
        failures = int(stats.get("failures", 0))

        if attempts == 0:
            return 0

        success_rate = successes / attempts

        bonus = int(success_rate * 10)
        penalty = failures * 5

        return bonus - penalty

    def decide(self) -> Dict[str, Any]:
        optimizer = self.optimizer.snapshot()
        forecast = self.forecast.snapshot()

        optimizer_providers = optimizer.get("providers", {})
        forecast_providers = forecast.get("providers", {})

        decision = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "provider_arbitration",
            "selected_provider": None,
            "arbitration_state": "stable",
            "candidates": {},
            "reason": None,
        }

        ranked = []

        for name, data in optimizer_providers.items():
            forecast_data = forecast_providers.get(name, {})
            base_score = int(data.get("optimization_score", 0))
            strategy_bonus = self._strategy_bonus(name)

            risk = forecast_data.get("risk_level", "unknown")
            risk_penalty = 0

            if risk == "medium":
                risk_penalty = 10
            elif risk == "high":
                risk_penalty = 25
            elif risk == "critical":
                risk_penalty = 50
            elif risk == "cooldown":
                risk_penalty = 80

            final_score = max(0, base_score + strategy_bonus - risk_penalty)

            decision["candidates"][name] = {
                "base_score": base_score,
                "strategy_bonus": strategy_bonus,
                "risk_level": risk,
                "risk_penalty": risk_penalty,
                "final_score": final_score,
                "available": data.get("available", True),
            }

            ranked.append((-final_score, name))

        if ranked:
            selected = sorted(ranked)[0][1]
            decision["selected_provider"] = selected
            selected_data = decision["candidates"][selected]
            decision["reason"] = (
                f"selected_by_final_score:{selected_data['final_score']}"
            )

            if selected_data["final_score"] < 50:
                decision["arbitration_state"] = "degraded"
            elif selected_data["final_score"] < 75:
                decision["arbitration_state"] = "watch"

        return decision


if __name__ == "__main__":
    print(json.dumps(ProviderArbitration().decide(), ensure_ascii=False, indent=2))
