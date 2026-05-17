import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
COMPRESSION_PATH = MEMORY_DIR / "memory_compression_runtime.json"

SOURCES = {
    "learning_summary": MEMORY_DIR / "learning_summary.json",
    "failure_summary": MEMORY_DIR / "failure_summary.json",
    "outcome_correlation": MEMORY_DIR / "outcome_correlation_engine.json",
    "adaptive_learning_scoring": MEMORY_DIR / "adaptive_learning_scoring.json",
}


def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class MemoryCompressionRuntime:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def compress(self):
        data = {name: load_json(path) for name, path in SOURCES.items()}

        learning = data["learning_summary"]
        failures = data["failure_summary"]
        scoring = data["adaptive_learning_scoring"]
        correlation = data["outcome_correlation"]

        compressed = {
            "learning_state": learning.get("learning_state"),
            "top_strategy": learning.get("top_strategy"),
            "top_goal": learning.get("top_goal"),
            "risk_state": failures.get("risk_state"),
            "top_failure_category": failures.get("top_failure_category"),
            "top_affected_component": failures.get("top_affected_component"),
            "adaptive_learning_score": scoring.get("adaptive_learning_score"),
            "learning_signal": scoring.get("learning_state"),
            "correlation_recommendation": correlation.get("recommendation"),
        }

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "memory_compression_runtime",
            "bounded": True,
            "dangerous_autonomous_apply": False,
            "compression_mode": "safe_summary_only_memory_compression",
            "source_count": len(SOURCES),
            "compressed_memory": compressed,
            "compression_state": "ready",
            "discarded_detail_policy": "raw_runtime_detail_not_persisted",
            "result": "memory_compression_built",
        }

        COMPRESSION_PATH.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return result


if __name__ == "__main__":
    result = MemoryCompressionRuntime().compress()
    print(json.dumps(result, ensure_ascii=False, indent=2))
