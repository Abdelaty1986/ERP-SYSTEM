import json
import os
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
GRAPH_PATH = MEMORY_DIR / "fallback_graph_runtime.json"


class FallbackGraphRuntime:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def build_graph(self):
        providers = {
            "openrouter": {
                "has_key": bool(os.getenv("OPENROUTER_API_KEY")),
                "model": os.getenv("OPENROUTER_MODEL", "not_configured"),
                "priority": 1,
            },
            "gemini": {
                "has_key": bool(os.getenv("GEMINI_API_KEY")),
                "model": os.getenv("GEMINI_MODEL", "not_configured"),
                "priority": 2,
            },
            "groq": {
                "has_key": bool(os.getenv("GROQ_API_KEY")),
                "model": os.getenv("GROQ_MODEL", "not_configured"),
                "priority": 3,
            },
        }

        nodes = {}
        ready_nodes = []

        for name, data in providers.items():
            ready = data["has_key"] and data["model"] != "not_configured"
            nodes[name] = {
                **data,
                "ready": ready,
                "fallback_eligible": ready,
                "state": "ready" if ready else "standby_needs_model" if data["has_key"] else "unavailable",
            }
            if ready:
                ready_nodes.append(name)

        ordered = sorted(
            ready_nodes,
            key=lambda p: nodes[p]["priority"],
        )

        fallback_edges = []
        for idx, provider in enumerate(ordered):
            next_provider = ordered[idx + 1] if idx + 1 < len(ordered) else None
            fallback_edges.append({
                "from": provider,
                "to": next_provider,
                "edge_state": "active" if next_provider else "terminal",
            })

        graph = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "fallback_graph_runtime",
            "bounded": True,
            "dangerous_autonomous_apply": False,
            "graph_mode": "safe_provider_fallback_map",
            "nodes": nodes,
            "ready_nodes": ordered,
            "fallback_edges": fallback_edges,
            "fallback_depth": max(len(ordered) - 1, 0),
            "fallback_ready": len(ordered) >= 2,
            "primary_provider": ordered[0] if ordered else None,
            "result": "fallback_graph_built" if ordered else "no_ready_provider",
        }

        GRAPH_PATH.write_text(
            json.dumps(graph, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return graph


if __name__ == "__main__":
    result = FallbackGraphRuntime().build_graph()
    print(json.dumps(result, ensure_ascii=False, indent=2))
