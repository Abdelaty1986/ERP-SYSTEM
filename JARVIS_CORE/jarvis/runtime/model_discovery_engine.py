import json
import os
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
SNAPSHOT_PATH = MEMORY_DIR / "model_discovery_snapshot.json"


class ModelDiscoveryEngine:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def discover(self):
        providers = {
            "openrouter": {
                "enabled": bool(os.getenv("OPENROUTER_API_KEY")),
                "configured_model": os.getenv("OPENROUTER_MODEL", "not_configured"),
                "source": "env",
                "discovery_state": "configured" if os.getenv("OPENROUTER_API_KEY") else "missing_key",
            },
            "gemini": {
                "enabled": bool(os.getenv("GEMINI_API_KEY")),
                "configured_model": os.getenv("GEMINI_MODEL", "not_configured"),
                "source": "env",
                "discovery_state": "configured" if os.getenv("GEMINI_API_KEY") else "missing_key",
            },
            "groq": {
                "enabled": bool(os.getenv("GROQ_API_KEY")),
                "configured_model": os.getenv("GROQ_MODEL", "not_configured"),
                "source": "env",
                "discovery_state": "configured" if os.getenv("GROQ_API_KEY") else "missing_key",
            },
        }

        active = [
            name for name, data in providers.items()
            if data["enabled"] and data["configured_model"] != "not_configured"
        ]

        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "model_discovery_engine",
            "bounded": True,
            "dangerous_autonomous_apply": False,
            "discovery_mode": "safe_env_snapshot",
            "providers": providers,
            "active_provider_count": len(active),
            "active_providers": active,
            "result": "models_discovered" if active else "no_active_models_found",
        }

        SNAPSHOT_PATH.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return snapshot


if __name__ == "__main__":
    result = ModelDiscoveryEngine().discover()
    print(json.dumps(result, ensure_ascii=False, indent=2))
