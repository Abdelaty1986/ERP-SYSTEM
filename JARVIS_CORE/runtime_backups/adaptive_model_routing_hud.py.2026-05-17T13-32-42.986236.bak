import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"

DISCOVERY_PATH = MEMORY_DIR / "model_discovery_snapshot.json"
VALIDATION_PATH = MEMORY_DIR / "provider_model_validation.json"
FALLBACK_PATH = MEMORY_DIR / "fallback_graph_runtime.json"
TRUST_PATH = MEMORY_DIR / "model_trust_memory.json"
HUD_PATH = MEMORY_DIR / "adaptive_model_routing_hud.json"


def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class AdaptiveModelRoutingHUD:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        discovery = load_json(DISCOVERY_PATH)
        validation = load_json(VALIDATION_PATH)
        fallback = load_json(FALLBACK_PATH)
        trust = load_json(TRUST_PATH)

        trust_ranking = trust.get("trust_ranking", [])
        ready_providers = validation.get("ready_providers", [])
        fallback_ready = fallback.get("fallback_ready", False)

        recommended_provider = None

        for item in trust_ranking:
            provider = item.get("provider")
            if provider in ready_providers:
                recommended_provider = provider
                break

        hud = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "adaptive_model_routing_hud",
            "bounded": True,
            "dangerous_autonomous_apply": False,
            "hud_mode": "safe_runtime_visibility",
            "adaptive_routing_decision": {
                "recommended_provider": recommended_provider,
                "decision_state": "ready" if recommended_provider else "no_ready_provider",
                "fallback_mode": "multi_provider" if fallback_ready else "single_provider_terminal",
            },
            "result": "adaptive_model_routing_hud_built",
        }

        HUD_PATH.write_text(
            json.dumps(hud, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return hud


if __name__ == "__main__":
    result = AdaptiveModelRoutingHUD().build()
    print(json.dumps(result, ensure_ascii=False, indent=2))
