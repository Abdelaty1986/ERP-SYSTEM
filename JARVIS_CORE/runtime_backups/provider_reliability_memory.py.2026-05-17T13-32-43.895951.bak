import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any


class ProviderReliabilityMemory:
    def __init__(self, memory_path: str = "JARVIS_CORE/runtime_memory/provider_reliability_memory.json"):
        self.memory_path = Path(memory_path)
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _default_provider(self) -> Dict[str, Any]:
        return {
            "success_count": 0,
            "failure_count": 0,
            "health_score": 100,
            "last_success": None,
            "last_failure": None,
            "last_error": None,
            "last_latency_ms": None,
            "average_latency_ms": None,
            "cooldown_until": None,
        }

    def _load(self) -> Dict[str, Any]:
        if not self.memory_path.exists():
            return {"providers": {}}

        try:
            return json.loads(self.memory_path.read_text(encoding="utf-8"))
        except Exception:
            return {"providers": {}}

    def save(self) -> None:
        self.memory_path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def ensure_provider(self, name: str) -> Dict[str, Any]:
        providers = self.data.setdefault("providers", {})
        if name not in providers:
            providers[name] = self._default_provider()
        return providers[name]

    def record_success(self, name: str, latency_ms: int | None = None) -> None:
        provider = self.ensure_provider(name)

        provider["success_count"] += 1
        provider["last_success"] = self._now()
        provider["last_error"] = None
        provider["cooldown_until"] = None
        provider["health_score"] = min(100, int(provider["health_score"]) + 5)

        if latency_ms is not None:
            provider["last_latency_ms"] = latency_ms
            avg = provider.get("average_latency_ms")
            if avg is None:
                provider["average_latency_ms"] = latency_ms
            else:
                provider["average_latency_ms"] = int((avg + latency_ms) / 2)

        self.save()

    def record_failure(
        self,
        name: str,
        error: str | None = None,
        cooldown_seconds: int = 300
    ) -> None:
        provider = self.ensure_provider(name)

        provider["failure_count"] += 1
        provider["last_failure"] = self._now()
        provider["last_error"] = error
        provider["health_score"] = max(0, int(provider["health_score"]) - 25)

        now = datetime.now(timezone.utc)
        cooldown_until = now.timestamp() + cooldown_seconds
        provider["cooldown_until"] = datetime.fromtimestamp(
            cooldown_until,
            tz=timezone.utc
        ).isoformat()

        self.save()


    def is_available(self, name: str) -> bool:
        provider = self.ensure_provider(name)
        cooldown_until = provider.get("cooldown_until")

        if not cooldown_until:
            return True

        try:
            cooldown_time = datetime.fromisoformat(cooldown_until)
            return datetime.now(timezone.utc) >= cooldown_time
        except Exception:
            return True

    def provider_rank(self, name: str) -> tuple:
        provider = self.ensure_provider(name)

        health = int(provider.get("health_score", 100))
        avg_latency = provider.get("average_latency_ms")

        if avg_latency is None:
            avg_latency = 999999

        available_penalty = 0 if self.is_available(name) else 1

        return (
            available_penalty,
            -health,
            int(avg_latency),
            int(provider.get("failure_count", 0)),
        )

    def get_provider(self, name: str) -> Dict[str, Any]:
        return self.ensure_provider(name)

    def list_providers(self) -> Dict[str, Any]:
        return self.data.setdefault("providers", {})


if __name__ == "__main__":
    memory = ProviderReliabilityMemory()
    memory.record_success("gemini", latency_ms=120)
    memory.record_failure("openrouter", error="test_failure", cooldown_seconds=60)
    print(json.dumps(memory.list_providers(), ensure_ascii=False, indent=2))
