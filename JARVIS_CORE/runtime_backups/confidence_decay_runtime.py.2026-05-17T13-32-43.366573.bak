import json
from datetime import datetime, timezone

from jarvis.runtime.provider_trust_memory import ProviderTrustMemory


class ConfidenceDecayRuntime:
    """
    Temporal confidence decay runtime.

    الهدف:
    - prevent stale provider trust
    - adaptive trust aging
    - bounded temporal cognition
    """

    def __init__(self):
        self.runtime = "confidence_decay_runtime"
        self.bounded = True
        self.autonomous_apply = False

    def apply_decay(self):
        memory_runtime = ProviderTrustMemory()
        memory = memory_runtime.load()

        providers = memory.get("providers", {})

        now = datetime.now(timezone.utc)

        decay_results = []

        for name, provider in providers.items():
            trust_score = provider.get("trust_score", 0)
            updated_at = provider.get("last_updated")

            if not updated_at:
                continue

            try:
                updated_dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            except Exception:
                continue

            age_hours = (
                now - updated_dt
            ).total_seconds() / 3600

            decay_factor = min(
                0.25,
                age_hours * 0.01
            )

            new_score = round(
                max(
                    0.05,
                    trust_score - decay_factor
                ),
                3
            )

            provider["trust_score"] = new_score
            provider["decay_applied"] = round(decay_factor, 3)
            provider["last_decay_run"] = now.isoformat()

            decay_results.append({
                "provider": name,
                "old_score": trust_score,
                "new_score": new_score,
                "decay_factor": round(decay_factor, 3),
                "age_hours": round(age_hours, 2),
            })

        memory["timestamp"] = now.isoformat()

        memory_runtime.save(memory)

        return {
            "runtime": self.runtime,
            "bounded": self.bounded,
            "autonomous_apply": self.autonomous_apply,
            "provider_count": len(decay_results),
            "decay_results": decay_results,
        }


if __name__ == "__main__":
    result = ConfidenceDecayRuntime().apply_decay()
    print(json.dumps(result, ensure_ascii=False, indent=2))
