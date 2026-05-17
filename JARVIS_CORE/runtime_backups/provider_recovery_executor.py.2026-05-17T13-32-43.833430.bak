import json
from datetime import datetime, timezone
from typing import Dict, Any

from jarvis.runtime.provider_recovery_planner import ProviderRecoveryPlanner
from jarvis.runtime.provider_router import ProviderRouter


class ProviderRecoveryExecutor:
    def __init__(self):
        self.planner = ProviderRecoveryPlanner()

    def execute(self, dry_run: bool = True) -> Dict[str, Any]:
        plan_snapshot = self.planner.plan()
        plans = plan_snapshot.get("plans", {})

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "provider_recovery_executor",
            "bounded": True,
            "dry_run": dry_run,
            "execution_state": "planning_only" if dry_run else "bounded_probe",
            "actions": {},
        }

        for name, plan in plans.items():
            recovery = plan.get("recommended_recovery")

            action_result = {
                "provider": name,
                "planned_recovery": recovery,
                "executed": False,
                "status": "skipped",
                "reason": plan.get("reason"),
            }

            if dry_run:
                action_result["status"] = "dry_run_only"

            elif recovery in ("wait_for_cooldown_expiry_then_probe", "latency_probe"):
                probe = ProviderRouter().think("Reply exactly: recovery_probe_ok")
                action_result.update({
                    "executed": True,
                    "status": "probe_executed",
                    "probe_provider": probe.get("provider"),
                    "probe_success": probe.get("result", {}).get("enabled") is True,
                    "fallback_used": probe.get("fallback_used"),
                })

            elif recovery in ("none", None):
                action_result["status"] = "no_action_needed"

            else:
                action_result["status"] = "bounded_action_not_enabled_yet"

            result["actions"][name] = action_result

        return result


if __name__ == "__main__":
    executor = ProviderRecoveryExecutor()
    print(json.dumps(executor.execute(dry_run=True), ensure_ascii=False, indent=2))
