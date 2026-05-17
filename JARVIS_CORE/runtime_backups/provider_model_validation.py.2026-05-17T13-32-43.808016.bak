import json
import os
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
VALIDATION_PATH = MEMORY_DIR / "provider_model_validation.json"


class ProviderModelValidationRuntime:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def validate(self):
        providers = {
            "openrouter": {
                "has_key": bool(os.getenv("OPENROUTER_API_KEY")),
                "model": os.getenv("OPENROUTER_MODEL", "not_configured"),
            },
            "gemini": {
                "has_key": bool(os.getenv("GEMINI_API_KEY")),
                "model": os.getenv("GEMINI_MODEL", "not_configured"),
            },
            "groq": {
                "has_key": bool(os.getenv("GROQ_API_KEY")),
                "model": os.getenv("GROQ_MODEL", "not_configured"),
            },
        }

        validated = {}

        for name, data in providers.items():
            has_model = data["model"] != "not_configured"
            ready = data["has_key"] and has_model

            validated[name] = {
                **data,
                "has_model": has_model,
                "ready": ready,
                "confidence_score": 1.0 if ready else 0.35 if data["has_key"] else 0.0,
                "validation_state": "ready" if ready else "needs_model_config" if data["has_key"] else "missing_key",
            }

        ready_providers = [k for k, v in validated.items() if v["ready"]]

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "provider_model_validation",
            "bounded": True,
            "dangerous_autonomous_apply": False,
            "validation_mode": "safe_static_provider_check",
            "providers": validated,
            "ready_provider_count": len(ready_providers),
            "ready_providers": ready_providers,
            "fallback_ready": len(ready_providers) >= 2,
            "result": "validation_passed" if ready_providers else "validation_failed",
        }

        VALIDATION_PATH.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return result


if __name__ == "__main__":
    result = ProviderModelValidationRuntime().validate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
