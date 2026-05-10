import os
import json
import urllib.request

from jarvis.agents.base_agent import BaseAgent


class GroqAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Groq Free Agent",
            role="Fast AI Review and Suggestions",
            provider="groq",
            cost="free"
        )
        self.api_key = os.getenv("GROQ_API_KEY")
        self.model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

    def think(self, task):
        if not self.api_key:
            return {
                "agent": self.name,
                "task": task,
                "analysis": "GROQ_API_KEY is not set. Agent skipped safely.",
                "risk_level": "unknown",
                "enabled": False,
                "approved_for_direct_apply": False
            }

        url = "https://api.groq.com/openai/v1/chat/completions"

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a free-tier AI code reviewer inside Jarvis. "
                        "You must suggest only. Never apply changes directly. "
                        "Return concise risk analysis."
                    )
                },
                {
                    "role": "user",
                    "content": task
                }
            ],
            "temperature": 0.2
        }

        data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            url,
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
                "analysis": f"Groq Agent error: {error}",
                "risk_level": "unknown",
                "enabled": False,
                "approved_for_direct_apply": False
            }


if __name__ == "__main__":
    agent = GroqAgent()
    print(agent.info())
    print(agent.think("Review Jarvis Core architecture safely"))
