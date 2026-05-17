import json
from datetime import datetime, timezone
from typing import Dict, Any

from jarvis.runtime.provider_self_healing import ProviderSelfHealing


class ProviderRecoveryPlanner:
    def __init__(self):
        self.self_healing = ProviderSelfHealing()

    def _plan_for_provider(self, name: str, provider: Dict[str, Any]) -> Dict[str, Any]:
        action = provider.get("action", "unknown")
        risk = provider.get("risk_level", "unknown")
        health = int(provider.get("health_score", 100) or 100)
        failures = int(provider.get("failure_count", 0) or 0)

        plan = {
            "provider": name,
            "current_action": action,
            "risk_level": risk,
            "recommended_recovery": "none",
            "requires_human_approval": False,
            "bounded": True,
            "reason": "provider healthy or no recovery needed",
        }

        if action == "keep_in_cooldown":
            plan.update({
                "recommended_recovery": "wait_for_cooldown_expiry_then_probe",
                "requires_human_approval": False,
                "reason": "provider is cooling down after recent instability",
            })

        elif action == "enter_cooldown":
            plan.update({
                "recommended_recovery": "apply_cooldown",
                "requires_human_approval": False,
                "reason": "provider risk or health indicates temporary isolation",
            })

        elif action == "reduce_priority_and_monitor":
            plan.update({
                "recommended_recovery": "lower_selection_weight_and_monitor",
                "requires_human_approval": False,
                "reason": "provider has repeated failures but is not critical",
            })

        elif action == "monitor_latency":
            plan.update({
                "recommended_recovery": "latency_probe",
                "requires_human_approval": False,
                "reason": "provider latency needs bounded probing",
            })

        if health < 40 or failures >= 5 or risk == "critical":
            plan["requires_human_approval"] = True
            plan["reason"] = "provider is critical and recovery should be supervised"

        return plan

    def plan(self) -> Dict[str, Any]:
        snapshot = self.self_healing.snapshot()
        providers = snapshot.get("providers", {})

        plans = {
            name: self._plan_for_provider(name, data)
            for name, data in providers.items()
        }

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "provider_recovery_planner",
            "healing_state": snapshot.get("healing_state"),
            "overall_state": snapshot.get("overall_state"),
            "selected_provider": snapshot.get("selected_provider"),
            "bounded": True,
            "execution_mode": "planning_only",
            "plans": plans,
        }


if __name__ == "__main__":
    print(json.dumps(ProviderRecoveryPlanner().plan(), ensure_ascii=False, indent=2))
