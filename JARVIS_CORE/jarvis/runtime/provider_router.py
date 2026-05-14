from jarvis.runtime.provider_registry import ProviderRegistry

from jarvis.agents.gemini_agent import GeminiAgent
from jarvis.agents.groq_agent import GroqAgent
from jarvis.agents.openrouter_agent import OpenRouterAgent


class ProviderRouter:
    def __init__(self):
        self.registry = ProviderRegistry()

        self.providers = {
            "gemini": GeminiAgent,
            "groq": GroqAgent,
            "openrouter": OpenRouterAgent,
        }

    def think(self, task: str):
        attempted = []

        for provider in self.registry.available_providers():
            name = provider.name
            attempted.append(name)

            try:
                agent_class = self.providers[name]
                agent = agent_class()

                result = agent.think(task)

                analysis = str(result.get("analysis", "")).lower()

                if (
                    "error" in analysis
                    or result.get("enabled") is False
                ):
                    self.registry.mark_failure(name)
                    continue

                self.registry.mark_success(name)

                return {
                    "provider": name,
                    "attempted": attempted,
                    "result": result,
                    "fallback_used": len(attempted) > 1,
                }

            except Exception as e:
                self.registry.mark_failure(name)

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
