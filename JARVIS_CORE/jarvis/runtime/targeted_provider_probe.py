import json
from datetime import datetime, timezone

from jarvis.agents.gemini_agent import GeminiAgent
from jarvis.agents.groq_agent import GroqAgent
from jarvis.agents.openrouter_agent import OpenRouterAgent


class TargetedProviderProbe:
    """
    Bounded targeted provider probe runtime.

    الهدف:
    - direct provider validation
    - provider-specific probing
    - bounded monitored execution
    - no dangerous autonomous apply
    """

    def __init__(self):
        self.runtime = "targeted_provider_probe"
        self.bounded = True
        self.autonomous_apply = False

    def _build_agent(self, provider_name):
        provider_name = provider_name.lower()

        mapping = {
            "gemini": GeminiAgent,
            "groq": GroqAgent,
            "openrouter": OpenRouterAgent,
        }

        agent_class = mapping.get(provider_name)

        if not agent_class:
            raise ValueError(f"Unsupported provider: {provider_name}")

        return agent_class()

    def execute(self, provider_name, dry_run=True):
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": self.runtime,
            "provider": provider_name,
            "bounded": self.bounded,
            "dry_run": dry_run,
            "autonomous_apply": self.autonomous_apply,
            "execution_state": (
                "planning_only"
                if dry_run
                else "bounded_targeted_probe"
            ),
            "probe_result": {
                "provider": provider_name,
                "probe_attempted": False,
                "probe_success": None,
                "risk_level": "low",
                "rollback_required": False,
                "response_excerpt": None,
            },
        }

        if dry_run:
            return result

        try:
            agent = self._build_agent(provider_name)

            response = agent.think(
                "Reply exactly with: provider_online"
            )

            response_text = str(response)
            analysis_text = ""

            if isinstance(response, dict):
                analysis_text = str(response.get("analysis", ""))
                enabled = bool(response.get("enabled", False))
            else:
                analysis_text = response_text
                enabled = True

            success = (
                enabled
                and analysis_text.strip().lower() == "provider_online"
            )

            result["probe_result"].update({
                "probe_attempted": True,
                "probe_success": success,
                "provider_enabled": enabled,
                "analysis_excerpt": analysis_text[:300],
                "response_excerpt": response_text[:300],
            })

        except Exception as exc:
            result["probe_result"].update({
                "probe_attempted": True,
                "probe_success": False,
                "response_excerpt": str(exc),
            })

        return result


if __name__ == "__main__":
    probe = TargetedProviderProbe()

    providers = [
        "gemini",
        "groq",
        "openrouter",
    ]

    results = []

    for provider in providers:
        results.append(
            probe.execute(
                provider_name=provider,
                dry_run=False,
            )
        )

    print(json.dumps({
        "runtime": "multi_targeted_provider_probe",
        "bounded": True,
        "provider_count": len(results),
        "results": results,
    }, ensure_ascii=False, indent=2))
