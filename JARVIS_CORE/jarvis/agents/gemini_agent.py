import os
import json
import urllib.request

from jarvis.agents.base_agent import BaseAgent


class GeminiAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Gemini Free Agent",
            role="Architecture and Planning Assistant",
            provider="google_gemini",
            cost="free"
        )

        self.api_key = os.getenv("GEMINI_API_KEY")

        self.url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.5-flash-lite:generateContent"
        )

    def think(self, task):
        if not self.api_key:
            return {
                "agent": self.name,
                "task": task,
                "analysis": (
                    "GEMINI_API_KEY is not set. "
                    "Agent skipped safely."
                ),
                "risk_level": "unknown",
                "enabled": False,
                "approved_for_direct_apply": False
            }

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "You are Jarvis planning assistant. "
                                "Analyze this task safely and briefly:\n\n"
                                f"{task}"
                            )
                        }
                    ]
                }
            ]
        }

        data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            f"{self.url}?key={self.api_key}",
            data=data,
            headers={
                "Content-Type": "application/json"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))

            content = result["candidates"][0]["content"]["parts"][0]["text"]

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
                "analysis": f"Gemini Agent error: {error}",
                "risk_level": "unknown",
                "enabled": False,
                "approved_for_direct_apply": False
            }


if __name__ == "__main__":
    agent = GeminiAgent()

    print(agent.info())

    print(
        agent.think(
            "Review Jarvis architecture safely"
        )
    )
