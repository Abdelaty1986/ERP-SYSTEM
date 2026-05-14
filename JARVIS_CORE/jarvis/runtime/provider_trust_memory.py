import json
from pathlib import Path
from datetime import datetime, timezone


MEMORY_PATH = Path(
    "JARVIS_CORE/runtime_memory/provider_trust_memory.json"
)


class ProviderTrustMemory:
    """
    Runtime provider trust evolution memory.

    الهدف:
    - track provider reliability
    - track recovery evolution
    - bounded adaptive trust scoring
    """

    def __init__(self):
        self.memory_path = MEMORY_PATH

    def _default_memory(self):
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "providers": {}
        }

    def load(self):
        if not self.memory_path.exists():
            return self._default_memory()

        try:
            return json.loads(
                self.memory_path.read_text(encoding="utf-8")
            )

        except Exception:
            return self._default_memory()

    def save(self, memory):
        self.memory_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.memory_path.write_text(
            json.dumps(memory, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def update_provider(
        self,
        provider_name,
        recovery_state,
        confidence,
    ):
        memory = self.load()

        providers = memory.setdefault("providers", {})

        provider = providers.setdefault(provider_name, {
            "success_count": 0,
            "failure_count": 0,
            "rate_limited_count": 0,
            "missing_credentials_count": 0,
            "degraded_count": 0,
            "trust_score": 0.5,
            "last_state": "unknown",
            "last_confidence": 0,
            "last_updated": None,
        })

        if recovery_state == "healthy":
            provider["success_count"] += 1

        else:
            provider["failure_count"] += 1

        if recovery_state == "rate_limited":
            provider["rate_limited_count"] += 1

        elif recovery_state == "missing_credentials":
            provider["missing_credentials_count"] += 1

        elif recovery_state == "degraded":
            provider["degraded_count"] += 1

        provider["trust_score"] = round(
            (
                provider["trust_score"] * 0.7
                + confidence * 0.3
            ),
            3
        )

        provider["last_state"] = recovery_state
        provider["last_confidence"] = confidence
        provider["last_updated"] = datetime.now(
            timezone.utc
        ).isoformat()

        memory["timestamp"] = datetime.now(
            timezone.utc
        ).isoformat()

        self.save(memory)

        return provider


if __name__ == "__main__":
    memory = ProviderTrustMemory()

    result = memory.update_provider(
        provider_name="gemini",
        recovery_state="healthy",
        confidence=0.95,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
