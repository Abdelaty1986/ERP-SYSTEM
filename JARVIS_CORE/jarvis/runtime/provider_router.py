from jarvis.runtime.provider_registry import ProviderRegistry
from jarvis.runtime.provider_reliability_memory import ProviderReliabilityMemory
from time import perf_counter

from jarvis.agents.gemini_agent import GeminiAgent
from jarvis.agents.groq_agent import GroqAgent
from jarvis.agents.openrouter_agent import OpenRouterAgent


class ProviderRouter:
    def __init__(self):
        self.registry = ProviderRegistry()
        self.reliability_memory = ProviderReliabilityMemory()

        self.providers = {
            "gemini": GeminiAgent,
            "groq": GroqAgent,
            "openrouter": OpenRouterAgent,
        }

    def think(self, task: str):
        attempted = []

        available = [
            p for p in self.registry.available_providers()
            if self.reliability_memory.is_available(p.name)
        ]

        available = sorted(
            available,
            key=lambda p: self.reliability_memory.provider_rank(p.name)
        )

        for provider in available:
            name = provider.name
            attempted.append(name)

            try:
                agent_class = self.providers[name]
                agent = agent_class()

                start = perf_counter()
                result = agent.think(task)
                latency_ms = int((perf_counter() - start) * 1000)

                analysis = str(result.get("analysis", "")).lower()

                if (
                    "error" in analysis
                    or result.get("enabled") is False
                ):
                    self.registry.mark_failure(name)
                    self.reliability_memory.record_failure(name, error=result.get('analysis'))
                    continue

                self.registry.mark_success(name)
                self.reliability_memory.record_success(name, latency_ms=latency_ms)

                return {
                    "provider": name,
                    "attempted": attempted,
                    "result": result,
                    "fallback_used": len(attempted) > 1,
                }

            except Exception as e:
                self.registry.mark_failure(name)
                self.reliability_memory.record_failure(name, error=str(e))

        return {
            "provider": None,
            "attempted": attempted,
            "result": {
                "analysis": "All providers failed"
            },
            "fallback_used": True,
        }


if __name__ == "__main__":
    router = ProviderRouter()

    result = router.think("Reply exactly: runtime_online")

    print(result)
