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

            normalized_analysis = analysis_text.strip().lower()

            success = (
                enabled
                and normalized_analysis == "provider_online"
            )

            recovery_state = "unavailable"

            if success:
                recovery_state = "healthy"

            elif "api_key" in normalized_analysis:
                recovery_state = "missing_credentials"

            elif "429" in normalized_analysis:
                recovery_state = "rate_limited"

            elif "404" in normalized_analysis:
                recovery_state = "model_unavailable"

            elif enabled:
                recovery_state = "degraded"

            confidence_score = 0.15

            if recovery_state == "healthy":
                confidence_score = 0.95

            elif recovery_state == "rate_limited":
                confidence_score = 0.70

            elif recovery_state == "degraded":
                confidence_score = 0.45

            elif recovery_state == "model_unavailable":
                confidence_score = 0.30

            result["probe_result"].update({
                "probe_attempted": True,
                "probe_success": success,
                "provider_enabled": enabled,
                "recovery_state": recovery_state,
                "recovery_confidence": confidence_score,
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

    healthy_count = 0
    degraded_count = 0

    best_provider = None
    best_confidence = -1

    for item in results:
        probe = item.get("probe_result", {})

        confidence = probe.get("recovery_confidence", 0)
        state = probe.get("recovery_state")

        if state == "healthy":
            healthy_count += 1
        else:
            degraded_count += 1

        if confidence > best_confidence:
            best_confidence = confidence
            best_provider = item.get("provider")

    summary = {
        "healthy_provider_count": healthy_count,
        "degraded_provider_count": degraded_count,
        "recommended_provider": best_provider,
        "recommended_confidence": best_confidence,
        "runtime_state": (
            "stable"
            if healthy_count > 0
            else "degraded"
        ),
    }

    print(json.dumps({
        "runtime": "multi_targeted_provider_probe",
        "bounded": True,
        "provider_count": len(results),
        "summary": summary,
        "results": results,
    }, ensure_ascii=False, indent=2))
