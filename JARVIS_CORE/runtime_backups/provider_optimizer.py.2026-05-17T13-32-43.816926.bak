import json
from datetime import datetime, timezone
from typing import Dict, Any

from jarvis.runtime.provider_intelligence import ProviderIntelligence
from jarvis.runtime.provider_forecast import ProviderForecast


class ProviderOptimizer:
    def __init__(self):
        self.intelligence = ProviderIntelligence()
        self.forecast = ProviderForecast()

    def _score_provider(self, name: str, provider: Dict[str, Any], forecast: Dict[str, Any]) -> int:
        score = int(provider.get("health_score", 100))

        latency = provider.get("average_latency_ms")
        failures = int(provider.get("failure_count", 0))
        available = provider.get("available", True)
        risk = forecast.get("risk_level", "low")

        if not available:
            score -= 60

        if latency is None:
            score -= 5
        elif latency <= 1200:
            score += 10
        elif latency <= 3000:
            score += 0
        elif latency <= 5000:
            score -= 15
        else:
            score -= 30

        score -= failures * 10

        if risk == "medium":
            score -= 15
        elif risk == "high":
            score -= 35
        elif risk == "critical":
            score -= 60
        elif risk == "cooldown":
            score -= 80

        return max(0, min(150, score))

    def snapshot(self) -> Dict[str, Any]:
        intelligence = self.intelligence.snapshot()
        forecast = self.forecast.snapshot()

        providers = intelligence.get("providers", {})
        forecast_providers = forecast.get("providers", {})

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "provider_optimizer",
            "providers": {},
            "recommended_provider": None,
            "optimization_state": "stable",
        }

        ranked = []

        for name, provider in providers.items():
            provider_forecast = forecast_providers.get(name, {})
            score = self._score_provider(name, provider, provider_forecast)

            result["providers"][name] = {
                "optimization_score": score,
                "health_score": provider.get("health_score"),
                "average_latency_ms": provider.get("average_latency_ms"),
                "failure_count": provider.get("failure_count"),
                "risk_level": provider_forecast.get("risk_level", "unknown"),
                "recommendation": provider_forecast.get("recommendation", "unknown"),
                "available": provider.get("available"),
            }

            ranked.append((-score, name))

        if ranked:
            result["recommended_provider"] = sorted(ranked)[0][1]

        scores = [p["optimization_score"] for p in result["providers"].values()]
        if scores and max(scores) < 50:
            result["optimization_state"] = "degraded"
        elif scores and max(scores) < 75:
            result["optimization_state"] = "watch"

        return result


if __name__ == "__main__":
    print(json.dumps(ProviderOptimizer().snapshot(), ensure_ascii=False, indent=2))
