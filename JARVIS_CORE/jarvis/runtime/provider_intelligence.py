import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

from jarvis.runtime.provider_reliability_memory import ProviderReliabilityMemory


class ProviderIntelligence:
    def __init__(self):
        self.memory = ProviderReliabilityMemory()

    def _stability_label(self, provider: Dict[str, Any]) -> str:
        health = int(provider.get("health_score", 100))
        failures = int(provider.get("failure_count", 0))

        if health >= 90 and failures == 0:
            return "stable"
        if health >= 70:
            return "watch"
        if health >= 40:
            return "degraded"
        return "critical"

    def _speed_label(self, provider: Dict[str, Any]) -> str:
        avg = provider.get("average_latency_ms")

        if avg is None:
            return "unknown"
        if avg <= 1200:
            return "fast"
        if avg <= 3000:
            return "normal"
        return "slow"

    def snapshot(self) -> Dict[str, Any]:
        providers = self.memory.list_providers()

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "provider_intelligence",
            "providers": {},
            "recommended_provider": None,
        }

        ranked = []

        for name, data in providers.items():
            available = self.memory.is_available(name)
            stability = self._stability_label(data)
            speed = self._speed_label(data)

            item = {
                "available": available,
                "health_score": data.get("health_score", 100),
                "success_count": data.get("success_count", 0),
                "failure_count": data.get("failure_count", 0),
                "average_latency_ms": data.get("average_latency_ms"),
                "stability": stability,
                "speed": speed,
                "cooldown_until": data.get("cooldown_until"),
                "last_error": data.get("last_error"),
            }

            report["providers"][name] = item
            ranked.append((self.memory.provider_rank(name), name))

        if ranked:
            report["recommended_provider"] = sorted(ranked)[0][1]

        return report


if __name__ == "__main__":
    intelligence = ProviderIntelligence()
    print(json.dumps(intelligence.snapshot(), ensure_ascii=False, indent=2))
