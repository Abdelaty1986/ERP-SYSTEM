from datetime import datetime


class JarvisMobileControlCenter:
    """
    Lightweight mobile control center data provider for JARVIS.
    Reads actual execution mode from the mode manager.
    """

    def snapshot(self):
        from jarvis.runtime.execution_mode_manager import read_mode
        mode_data = read_mode()
        current_mode = mode_data.get("mode", "controlled_real_execution")

        return {
            "status": "online",
            "mode": current_mode,
            "voice": "enabled",
            "runtime": "ready",
            "agents": [
                "Local Reviewer",
                "Gemini",
                "Groq",
                "OpenRouter",
            ],
            "safety": {
                "sandbox": current_mode == "simulation_only",
                "rollback": True,
                "signed_receipts": True,
                "gated_apply": current_mode != "simulation_only",
            },
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
