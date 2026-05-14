import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any


class ProviderStrategyMemory:
    def __init__(
        self,
        memory_path: str = "JARVIS_CORE/runtime_memory/provider_strategy_memory.json"
    ):
        self.memory_path = Path(memory_path)
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.memory_path.exists():
            self._save({
                "strategies": []
            })

    def _load(self) -> Dict[str, Any]:
        try:
            return json.loads(
                self.memory_path.read_text(encoding="utf-8")
            )
        except Exception:
            return {"strategies": []}

    def _save(self, data: Dict[str, Any]):
        self.memory_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def record_strategy(
        self,
        provider: str,
        optimization_score: int,
        success: bool,
        latency_ms: int | None = None,
        reason: str | None = None,
    ):
        data = self._load()

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": provider,
            "optimization_score": optimization_score,
            "success": success,
            "latency_ms": latency_ms,
            "reason": reason,
        }

        data["strategies"].append(entry)

        data["strategies"] = data["strategies"][-200:]

        self._save(data)

    def summary(self) -> Dict[str, Any]:
        data = self._load()
        strategies = data.get("strategies", [])

        provider_stats = {}

        for s in strategies:
            name = s.get("provider")

            if name not in provider_stats:
                provider_stats[name] = {
                    "attempts": 0,
                    "successes": 0,
                    "failures": 0,
                    "average_score": 0,
                }

            stats = provider_stats[name]

            stats["attempts"] += 1

            if s.get("success"):
                stats["successes"] += 1
            else:
                stats["failures"] += 1

            scores = [
                x.get("optimization_score", 0)
                for x in strategies
                if x.get("provider") == name
            ]

            if scores:
                stats["average_score"] = int(sum(scores) / len(scores))

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "provider_strategy_memory",
            "total_records": len(strategies),
            "providers": provider_stats,
        }


if __name__ == "__main__":
    memory = ProviderStrategyMemory()

    memory.record_strategy(
        provider="gemini",
        optimization_score=100,
        success=True,
        latency_ms=1200,
        reason="optimizer_selected"
    )

    print(json.dumps(memory.summary(), ensure_ascii=False, indent=2))
