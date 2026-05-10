import os


class RealApplySwitch:
    """
    Controls whether real apply is allowed.
    Default is always disabled unless explicitly enabled by environment.
    """

    ENV_KEY = "JARVIS_ENABLE_REAL_APPLY"

    def status(self, mode_override=None):
        env_enabled = os.getenv(self.ENV_KEY, "").lower() in [
            "1",
            "true",
            "yes",
            "enabled",
        ]

        gated_enabled = mode_override == "gated_apply"
        enabled = env_enabled or gated_enabled

        mode = "gated_apply" if gated_enabled else (
            "real_apply_enabled" if env_enabled else "simulation_only"
        )

        return {
            "enabled": enabled,
            "can_apply_real_files": enabled,
            "mode": mode,
            "reason": (
                "Real apply explicitly enabled by gated CLI flag."
                if gated_enabled
                else (
                    "Real apply explicitly enabled by environment."
                    if env_enabled
                    else "Real apply disabled by default safety policy."
                )
            ),
        }
