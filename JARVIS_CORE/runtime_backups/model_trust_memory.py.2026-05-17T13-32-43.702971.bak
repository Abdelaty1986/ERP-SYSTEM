import json
import os
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
TRUST_PATH = MEMORY_DIR / "model_trust_memory.json"


class ModelTrustMemory:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        providers = {
            "openrouter": {
                "enabled": bool(os.getenv("OPENROUTER_API_KEY")),
                "model": os.getenv("OPENROUTER_MODEL", "not_configured"),
                "historical_stability": 0.92,
                "fallback_resilience": 0.88,
            },
            "gemini": {
                "enabled": bool(os.getenv("GEMINI_API_KEY")),
                "model": os.getenv("GEMINI_MODEL", "not_configured"),
                "historical_stability": 0.70,
                "fallback_resilience": 0.65,
            },
            "groq": {
                "enabled": bool(os.getenv("GROQ_API_KEY")),
                "model": os.getenv("GROQ_MODEL", "not_configured"),
                "historical_stability": 0.72,
                "fallback_resilience": 0.66,
            },
        }

        trust_memory = {}

        for name, data in providers.items():
            configured = (
                data["enabled"] and
                data["model"] != "not_configured"
            )

            trust_score = round(
                (
                    data["historical_stability"] * 0.6 +
                    data["fallback_resilience"] * 0.4
                ),
                2,
            )

            if not configured:
                trust_score *= 0.5

            trust_memory[name] = {
                **data,
                "configured": configured,
                "trust_score": round(trust_score, 2),
                "trust_state": (
                    "trusted"
                    if trust_score >= 0.8 else
                    "moderate" if trust_score >= 0.5 else
                    "low_confidence"
                ),
            }

        ranked = sorted(
            trust_memory.items(),
            key=lambda x: x[1]["trust_score"],
            reverse=True,
        )

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "model_trust_memory",
            "bounded": True,
            "dangerous_autonomous_apply": False,
            "trust_mode": "safe_static_trust_evaluation",
            "providers": trust_memory,
            "trust_ranking": [
                {
                    "provider": k,
                    "trust_score": v["trust_score"],
                }
                for k, v in ranked
            ],
            "primary_trusted_provider": ranked[0][0] if ranked else None,
            "result": "trust_memory_built",
        }

        TRUST_PATH.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return result


if __name__ == "__main__":
    result = ModelTrustMemory().build()
    print(json.dumps(result, ensure_ascii=False, indent=2))
