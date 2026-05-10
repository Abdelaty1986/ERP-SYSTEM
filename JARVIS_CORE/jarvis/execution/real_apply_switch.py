import os


class RealApplySwitch:
    """
    Controls whether real apply is allowed.
    Default is always disabled unless explicitly enabled by environment.
    """

    ENV_KEY = "JARVIS_ENABLE_REAL_APPLY"

    def status(self):
        enabled = os.getenv(self.ENV_KEY, "").lower() in [
            "1",
            "true",
            "yes",
            "enabled",
        ]

        return {
            "enabled": enabled,
            "can_apply_real_files": enabled,
            "mode": "real_apply_enabled" if enabled else "simulation_only",
            "reason": (
                "Real apply explicitly enabled by environment."
                if enabled
                else "Real apply disabled by default safety policy."
            ),
        }
