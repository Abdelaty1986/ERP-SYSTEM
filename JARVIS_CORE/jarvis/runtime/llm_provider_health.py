from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from jarvis.agents.gemini_agent import GeminiAgent
from jarvis.agents.groq_agent import GroqAgent
from jarvis.agents.openrouter_agent import OpenRouterAgent


class LLMProviderHealth:
    def __init__(self, root="JARVIS_CORE"):
        self.root = Path(root)
        self.output_file = (
            self.root / "runtime_logs" / "llm_provider_health.json"
        )

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def check_agent(self, name, agent):
        try:
            result = agent.think(
                "Reply with exactly: provider_online"
            )

            analysis = str(result.get("analysis", ""))

            ok = (
                result.get("enabled") is True
                and "provider_online" in analysis.lower()
            )

            return {
                "provider": name,
                "ok": ok,
                "enabled": result.get("enabled"),
                "status": "online" if ok else "unavailable",
                "message": analysis[:300],
            }

        except Exception as exc:
            return {
                "provider": name,
                "ok": False,
                "enabled": False,
                "status": "error",
                "message": str(exc),
            }

    def run(self):
        checks = [
            self.check_agent("gemini", GeminiAgent()),
            self.check_agent("groq", GroqAgent()),
            self.check_agent("openrouter", OpenRouterAgent()),
        ]

        online = [
            item for item in checks
            if item.get("ok")
        ]

        preferred = online[0]["provider"] if online else "local_runtime_brain"

        report = {
            "timestamp": self._now(),
            "health_check": "llm_provider_health",
            "bounded": True,
            "real_apply_enabled": False,
            "autonomous_apply": False,
            "preferred_provider": preferred,
            "online_count": len(online),
            "providers": checks,
            "fallback": "local_runtime_brain",
            "final_state": "online" if online else "local_only",
        }

        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.output_file.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return report


if __name__ == "__main__":
    print(json.dumps(
        LLMProviderHealth().run(),
        ensure_ascii=False,
        indent=2
    ))
