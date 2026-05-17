import json
from datetime import datetime, timezone
from typing import Dict, Any

from jarvis.runtime.provider_intelligence import ProviderIntelligence


class ProviderForecast:
    def __init__(self):
        self.intelligence = ProviderIntelligence()

    def _risk_level(self, provider: Dict[str, Any]) -> str:
        health = int(provider.get("health_score", 100))
        failures = int(provider.get("failure_count", 0))
        latency = provider.get("average_latency_ms")

        if not provider.get("available", True):
            return "cooldown"

        if health < 40 or failures >= 5:
            return "critical"

        if health < 70 or failures >= 3:
            return "high"

        if latency is not None and latency > 5000:
            return "medium"

        return "low"

    def _recommendation(self, risk: str) -> str:
        if risk == "cooldown":
            return "skip_provider_temporarily"
        if risk == "critical":
            return "avoid_provider"
        if risk == "high":
            return "prefer_fallback"
        if risk == "medium":
            return "monitor_latency"
        return "provider_healthy"

    def snapshot(self) -> Dict[str, Any]:
        intelligence = self.intelligence.snapshot()
        providers = intelligence.get("providers", {})

        forecast = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "provider_forecast",
            "recommended_provider": intelligence.get("recommended_provider"),
            "providers": {},
            "overall_state": "stable",
        }

        risks = []

        for name, provider in providers.items():
            risk = self._risk_level(provider)
            risks.append(risk)

            forecast["providers"][name] = {
                "risk_level": risk,
                "recommendation": self._recommendation(risk),
                "health_score": provider.get("health_score"),
                "average_latency_ms": provider.get("average_latency_ms"),
                "failure_count": provider.get("failure_count"),
                "available": provider.get("available"),
            }

        if "critical" in risks:
            forecast["overall_state"] = "critical"
        elif "high" in risks:
            forecast["overall_state"] = "unstable"
        elif "medium" in risks:
            forecast["overall_state"] = "watch"
        elif "cooldown" in risks:
            forecast["overall_state"] = "degraded"

        return forecast


if __name__ == "__main__":
    print(json.dumps(ProviderForecast().snapshot(), ensure_ascii=False, indent=2))
