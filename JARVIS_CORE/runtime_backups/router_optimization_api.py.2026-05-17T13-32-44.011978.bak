import json
from pathlib import Path

ROOT = Path("JARVIS_CORE")
MEMORY_FILE = ROOT / "runtime_memory" / "router_optimization_memory.json"


def get_router_optimization_status():
    if not MEMORY_FILE.exists():
        return {
            "available": False,
            "bounded": True,
            "state": "missing_memory"
        }

    try:
        data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "available": False,
            "bounded": True,
            "state": "read_error",
            "error": str(exc)
        }

    return {
        "available": True,
        "bounded": True,
        "runtime": data.get("runtime"),
        "optimization_state": data.get("optimization_state"),
        "ranking": data.get("ranking", []),
        "adaptive_decision": data.get("adaptive_decision", {}),
        "routing_history_count": len(data.get("routing_history", [])),
        "dangerous_autonomous_apply": data.get(
            "dangerous_autonomous_apply",
            False
        )
    }


if __name__ == "__main__":
    print(
        json.dumps(
            get_router_optimization_status(),
            ensure_ascii=False,
            indent=2
        )
    )
