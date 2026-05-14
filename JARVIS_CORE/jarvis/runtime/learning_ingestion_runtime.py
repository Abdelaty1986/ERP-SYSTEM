import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"

INGESTION_PATH = MEMORY_DIR / "learning_ingestion_runtime.json"


SOURCES = {
    "provider_validation": MEMORY_DIR / "provider_model_validation.json",
    "fallback_graph": MEMORY_DIR / "fallback_graph_runtime.json",
    "model_trust": MEMORY_DIR / "model_trust_memory.json",
    "adaptive_model_routing": MEMORY_DIR / "adaptive_model_routing_hud.json",
    "failure_summary": MEMORY_DIR / "failure_summary.json",
    "learning_summary": MEMORY_DIR / "learning_summary.json",
    "architecture_goals": LOGS_DIR / "architecture_goals.json",
}


def safe_load(path):
    if not path.exists():
        return {"exists": False, "data": None}

    try:
        return {
            "exists": True,
            "data": json.loads(path.read_text(encoding="utf-8")),
        }
    except Exception as exc:
        return {
            "exists": True,
            "data": None,
            "error": str(exc),
        }


class LearningIngestionRuntime:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def ingest(self):
        sources = {
            name: safe_load(path)
            for name, path in SOURCES.items()
        }

        available_sources = [
            name for name, payload in sources.items()
            if payload.get("exists") and payload.get("data") is not None
        ]

        missing_sources = [
            name for name, payload in sources.items()
            if not payload.get("exists")
        ]

        unreadable_sources = [
            name for name, payload in sources.items()
            if payload.get("exists") and payload.get("data") is None
        ]

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "learning_ingestion_runtime",
            "bounded": True,
            "dangerous_autonomous_apply": False,
            "ingestion_mode": "safe_read_only_runtime_snapshot",
            "available_source_count": len(available_sources),
            "available_sources": available_sources,
            "missing_sources": missing_sources,
            "unreadable_sources": unreadable_sources,
            "learning_ready": len(available_sources) > 0,
            "ingested_sources": sources,
            "result": "learning_ingestion_ready" if available_sources else "no_learning_sources_found",
        }

        INGESTION_PATH.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return result


if __name__ == "__main__":
    result = LearningIngestionRuntime().ingest()
    print(json.dumps(result, ensure_ascii=False, indent=2))
