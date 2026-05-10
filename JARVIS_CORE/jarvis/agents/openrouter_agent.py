import os
import json
import urllib.request

from jarvis.agents.base_agent import BaseAgent


class OpenRouterAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="OpenRouter Free Agent",
            role="Multi-Model Routing Assistant",
            provider="openrouter",
            cost="free"
        )

        self.api_key = os.getenv("OPENROUTER_API_KEY")

        self.model = os.getenv(
            "OPENROUTER_MODEL",
            "meta-llama/llama-3.1-8b-instruct:free"
        )

        self.url = "https://openrouter.ai/api/v1/chat/completions"

    def think(self, task):
        if not self.api_key:
            return {
                "agent": self.name,
                "task": task,
                "analysis": (
                    "OPENROUTER_API_KEY is not set. "
                    "Agent skipped safely."
                ),
                "risk_level": "unknown",
                "enabled": False,
                "approved_for_direct_apply": False
            }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Jarvis multi-model assistant. "
                        "Review tasks safely. "
                        "Never apply changes directly."
                    )
                },
                {
                    "role": "user",
                    "content": task
                }
            ]
        }

        data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            self.url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))

            content = result["choices"][0]["message"]["content"]

            return {
                "agent": self.name,
                "task": task,
                "analysis": content,
                "risk_level": "medium",
                "enabled": True,
                "approved_for_direct_apply": False
            }

        except Exception as error:
            return {
                "agent": self.name,
                "task": task,
                "analysis": f"OpenRouter Agent error: {error}",
                "risk_level": "unknown",
                "enabled": False,
                "approved_for_direct_apply": False
            }


if __name__ == "__main__":
    agent = OpenRouterAgent()

    print(agent.info())

    print(
        agent.think(
            "Review multi-agent architecture safely"
        )
    )
