import json

from jarvis.runtime.targeted_provider_probe import TargetedProviderProbe
from jarvis.runtime.provider_trust_memory import ProviderTrustMemory


def build_report():
    probe = TargetedProviderProbe()

    providers = [
        "gemini",
        "groq",
        "openrouter",
    ]

    trust_memory = ProviderTrustMemory()

    results = []

    for provider in providers:
        result = probe.execute(
            provider_name=provider,
            dry_run=False,
        )

        probe_result = result.get("probe_result", {})

        trust_memory.update_provider(
            provider_name=provider,
            recovery_state=probe_result.get(
                "recovery_state",
                "unknown",
            ),
            confidence=probe_result.get(
                "recovery_confidence",
                0,
            ),
        )

        results.append(result)

    healthy_count = 0
    degraded_count = 0
    best_provider = None
    best_confidence = -1

    for item in results:
        probe_result = item.get("probe_result", {})
        confidence = probe_result.get("recovery_confidence", 0)
        state = probe_result.get("recovery_state")

        if state == "healthy":
            healthy_count += 1
        else:
            degraded_count += 1

        if confidence > best_confidence:
            best_confidence = confidence
            best_provider = item.get("provider")

    return {
        "runtime": "targeted_provider_probe_report",
        "bounded": True,
        "provider_count": len(results),
        "summary": {
            "healthy_provider_count": healthy_count,
            "degraded_provider_count": degraded_count,
            "recommended_provider": best_provider,
            "recommended_confidence": best_confidence,
            "runtime_state": "stable" if healthy_count > 0 else "degraded",
        },
        "results": results,
    }


if __name__ == "__main__":
    print(json.dumps(build_report(), ensure_ascii=False, indent=2))
