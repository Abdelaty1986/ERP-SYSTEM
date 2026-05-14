import concurrent.futures
from jarvis.runtime.provider_registry import ProviderRegistry
from jarvis.runtime.provider_reliability_memory import ProviderReliabilityMemory
from jarvis.runtime.provider_optimizer import ProviderOptimizer
from jarvis.runtime.provider_arbitration import ProviderArbitration
from jarvis.runtime.provider_strategy_memory import ProviderStrategyMemory
from time import perf_counter

from jarvis.agents.gemini_agent import GeminiAgent
from jarvis.agents.groq_agent import GroqAgent
from jarvis.agents.openrouter_agent import OpenRouterAgent

PROVIDER_TIMEOUT_SECONDS = 20
MIN_PROVIDER_TIMEOUT_SECONDS = 8
MAX_PROVIDER_TIMEOUT_SECONDS = 30


class ProviderRouter:
    def __init__(self):
        self.registry = ProviderRegistry()
        self.reliability_memory = ProviderReliabilityMemory()
        self.optimizer = ProviderOptimizer()
        self.arbitration = ProviderArbitration()
        self.strategy_memory = ProviderStrategyMemory()

        self.providers = {
            "gemini": GeminiAgent,
            "groq": GroqAgent,
            "openrouter": OpenRouterAgent,
        }


    def _provider_timeout_seconds(self, name: str) -> int:
        provider = self.reliability_memory.get_provider(name)

        avg_latency = provider.get("average_latency_ms")
        failures = int(provider.get("failure_count", 0))

        timeout = PROVIDER_TIMEOUT_SECONDS

        if avg_latency is not None:
            timeout = int((avg_latency / 1000) * 3) + 5

        if failures >= 3:
            timeout = min(timeout, 12)

        return max(
            MIN_PROVIDER_TIMEOUT_SECONDS,
            min(MAX_PROVIDER_TIMEOUT_SECONDS, timeout)
        )


    def think(self, task: str):
        attempted = []

        available = [
            p for p in self.registry.available_providers()
            if self.reliability_memory.is_available(p.name)
        ]

        arbitration = self.arbitration.decide()
        arbitration_candidates = arbitration.get("candidates", {})

        available = sorted(
            available,
            key=lambda p: -int(
                arbitration_candidates.get(p.name, {}).get("final_score", 0)
            )
        )

        for provider in available:
            name = provider.name
            attempted.append(name)

            try:
                agent_class = self.providers[name]
                agent = agent_class()

                start = perf_counter()

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(agent.think, task)
                    try:
                        timeout_seconds = self._provider_timeout_seconds(name)
                        result = future.result(timeout=timeout_seconds)
                    except concurrent.futures.TimeoutError:
                        latency_ms = int((perf_counter() - start) * 1000)
                        self.registry.mark_failure(name)
                        self.reliability_memory.record_failure(
                            name,
                            error=f"provider_timeout_after_{timeout_seconds}s"
                        )

                        optimization_score = optimizer_providers.get(
                            name, {}
                        ).get("optimization_score", 0)

                        self.strategy_memory.record_strategy(
                            provider=name,
                            optimization_score=optimization_score,
                            success=False,
                            latency_ms=latency_ms,
                            reason=f"provider_timeout_after_{timeout_seconds}s"
                        )

                        continue

                latency_ms = int((perf_counter() - start) * 1000)

                analysis = str(result.get("analysis", "")).lower()

                if (
                    "error" in analysis
                    or result.get("enabled") is False
                ):
                    self.registry.mark_failure(name)
                    self.reliability_memory.record_failure(name, error=result.get('analysis'))

                    optimization_score = arbitration_candidates.get(
                        name, {}
                    ).get("final_score", 0)

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

                optimization_score = arbitration_candidates.get(
                    name, {}
                ).get("final_score", 0)

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
                    "arbitration_state": arbitration.get("arbitration_state"),
                    "arbitration_reason": arbitration.get("reason"),
                }

            except Exception as e:
                self.registry.mark_failure(name)
                self.reliability_memory.record_failure(name, error=str(e))

                optimization_score = arbitration_candidates.get(
                    name, {}
                ).get("final_score", 0)

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
