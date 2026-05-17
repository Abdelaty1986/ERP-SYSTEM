import json
from datetime import datetime, timezone
from typing import Dict, Any

from jarvis.runtime.provider_reliability_memory import ProviderReliabilityMemory
from jarvis.runtime.provider_forecast import ProviderForecast
from jarvis.runtime.provider_arbitration import ProviderArbitration


class ProviderSelfHealing:
    def __init__(self):
        self.reliability = ProviderReliabilityMemory()
        self.forecast = ProviderForecast()
        self.arbitration = ProviderArbitration()

    def _healing_action(self, name: str, reliability: Dict[str, Any], forecast: Dict[str, Any]) -> str:
        risk = forecast.get("risk_level", "unknown")
        health = int(reliability.get("health_score", 100))
        failures = int(reliability.get("failure_count", 0))
        cooldown_until = reliability.get("cooldown_until")

        if cooldown_until:
            return "keep_in_cooldown"

        if risk in ("critical", "high") or health < 50:
            return "enter_cooldown"

        if failures >= 3:
            return "reduce_priority_and_monitor"

        if risk == "medium":
            return "monitor_latency"

        return "healthy_no_action"

    def snapshot(self) -> Dict[str, Any]:
        forecast_snapshot = self.forecast.snapshot()
        arbitration_snapshot = self.arbitration.decide()
        providers = self.reliability.list_providers()

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "provider_self_healing",
            "selected_provider": arbitration_snapshot.get("selected_provider"),
            "overall_state": forecast_snapshot.get("overall_state"),
            "providers": {},
            "healing_state": "stable",
        }

        actions = []

        for name, reliability_data in providers.items():
            forecast_data = forecast_snapshot.get("providers", {}).get(name, {})
            action = self._healing_action(name, reliability_data, forecast_data)
            actions.append(action)

            result["providers"][name] = {
                "action": action,
                "health_score": reliability_data.get("health_score"),
                "failure_count": reliability_data.get("failure_count"),
                "average_latency_ms": reliability_data.get("average_latency_ms"),
                "risk_level": forecast_data.get("risk_level", "unknown"),
                "cooldown_until": reliability_data.get("cooldown_until"),
            }

        if any(a in ("enter_cooldown", "keep_in_cooldown") for a in actions):
            result["healing_state"] = "active"
        elif any(a in ("reduce_priority_and_monitor", "monitor_latency") for a in actions):
            result["healing_state"] = "watch"

        return result


if __name__ == "__main__":
    print(json.dumps(ProviderSelfHealing().snapshot(), ensure_ascii=False, indent=2))
