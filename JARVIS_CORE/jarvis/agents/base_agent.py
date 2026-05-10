class BaseAgent:
    def __init__(self, name, role, provider="local", cost="free"):
        self.name = name
        self.role = role
        self.provider = provider
        self.cost = cost

        if self.cost != "free":
            raise ValueError("Jarvis allows free agents only.")

    def info(self):
        return {
            "name": self.name,
            "role": self.role,
            "provider": self.provider,
            "cost": self.cost
        }

    def think(self, task):
        raise NotImplementedError(
            "Agents must implement the think() method."
        )
