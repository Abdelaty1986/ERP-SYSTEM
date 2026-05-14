import json

from jarvis.runtime.provider_trust_memory import ProviderTrustMemory
from jarvis.runtime.confidence_decay_runtime import ConfidenceDecayRuntime


def build_report(apply_decay=True):
    if apply_decay:
        ConfidenceDecayRuntime().apply_decay()

    memory = ProviderTrustMemory().load()
    providers = memory.get("providers", {})

    ranked = sorted(
        providers.items(),
        key=lambda item: item[1].get("trust_score", 0),
        reverse=True,
    )

    return {
        "runtime": "provider_trust_report",
        "bounded": True,
        "provider_count": len(providers),
        "top_provider": ranked[0][0] if ranked else None,
        "providers": dict(ranked),
        "timestamp": memory.get("timestamp"),
    }


if __name__ == "__main__":
    print(json.dumps(build_report(), ensure_ascii=False, indent=2))
