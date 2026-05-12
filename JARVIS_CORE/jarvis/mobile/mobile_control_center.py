from datetime import datetime


class JarvisMobileControlCenter:
    """
    Lightweight mobile control center data provider for JARVIS.
    """

    def snapshot(self):
        return {
            "status": "online",
            "mode": "simulation_ready",
            "voice": "enabled",
            "runtime": "ready",
            "agents": [
                "Local Reviewer",
                "Gemini",
                "Groq",
                "OpenRouter",
            ],
            "safety": {
                "sandbox": True,
                "rollback": True,
                "signed_receipts": True,
                "gated_apply": True,
            },
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
