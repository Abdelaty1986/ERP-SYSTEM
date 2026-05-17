from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Any


@dataclass
class ProviderState:
    name: str
    enabled: bool
    priority: int
    health_score: int = 100
    cooldown: bool = False
    last_failure: str | None = None
    last_success: str | None = None


class ProviderRegistry:
    def __init__(self):
        self.providers: Dict[str, ProviderState] = {
            "gemini": ProviderState("gemini", True, 1),
            "groq": ProviderState("groq", True, 2),
            "openrouter": ProviderState("openrouter", True, 3),
        }

    def list_providers(self) -> Dict[str, Any]:
        return {name: asdict(state) for name, state in self.providers.items()}

    def available_providers(self):
        return sorted(
            [
                p for p in self.providers.values()
                if p.enabled and not p.cooldown and p.health_score > 0
            ],
            key=lambda p: p.priority
        )

    def mark_success(self, name: str):
        if name not in self.providers:
            return False
        self.providers[name].last_success = datetime.now(timezone.utc).isoformat()
        self.providers[name].cooldown = False
        self.providers[name].health_score = min(100, self.providers[name].health_score + 5)
        return True

    def mark_failure(self, name: str):
        if name not in self.providers:
            return False
        self.providers[name].last_failure = datetime.now(timezone.utc).isoformat()
        self.providers[name].health_score = max(0, self.providers[name].health_score - 25)
        if self.providers[name].health_score <= 50:
            self.providers[name].cooldown = True
        return True


if __name__ == "__main__":
    registry = ProviderRegistry()
    print(registry.list_providers())
    print([p.name for p in registry.available_providers()])
