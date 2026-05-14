from jarvis.runtime.provider_registry import ProviderRegistry
from jarvis.runtime.provider_reliability_memory import ProviderReliabilityMemory
from jarvis.runtime.provider_optimizer import ProviderOptimizer
from jarvis.runtime.provider_strategy_memory import ProviderStrategyMemory
from time import perf_counter

from jarvis.agents.gemini_agent import GeminiAgent
from jarvis.agents.groq_agent import GroqAgent
from jarvis.agents.openrouter_agent import OpenRouterAgent


class ProviderRouter:
    def __init__(self):
        self.registry = ProviderRegistry()
        self.reliability_memory = ProviderReliabilityMemory()
        self.optimizer = ProviderOptimizer()
        self.strategy_memory = ProviderStrategyMemory()

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

        optimizer_snapshot = self.optimizer.snapshot()
        optimizer_providers = optimizer_snapshot.get("providers", {})

        available = sorted(
            available,
            key=lambda p: -int(
                optimizer_providers.get(p.name, {}).get("optimization_score", 0)
            )
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

                    optimization_score = optimizer_providers.get(
                        name, {}
                    ).get("optimization_score", 0)

                    self.strategy_memory.record_strategy(
                        provider=name,
                        optimization_score=optimization_score,
                        success=False,
                        latency_ms=latency_ms,
                        reason="provider_returned_error"
                    )

                    continue

                self.registry.mark_success(name)
                self.reliability_memory.record_success(name, latency_ms=latency_ms)

                optimization_score = optimizer_providers.get(
                    name, {}
                ).get("optimization_score", 0)

                self.strategy_memory.record_strategy(
                    provider=name,
                    optimization_score=optimization_score,
                    success=True,
                    latency_ms=latency_ms,
                    reason="optimizer_router_selection"
                )

                return {
                    "provider": name,
                    "attempted": attempted,
                    "result": result,
                    "fallback_used": len(attempted) > 1,
                }

            except Exception as e:
                self.registry.mark_failure(name)
                self.reliability_memory.record_failure(name, error=str(e))

                optimization_score = optimizer_providers.get(
                    name, {}
                ).get("optimization_score", 0)

                self.strategy_memory.record_strategy(
                    provider=name,
                    optimization_score=optimization_score,
                    success=False,
                    latency_ms=None,
                    reason=str(e)
                )

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
