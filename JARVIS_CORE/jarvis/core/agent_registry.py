import json
from pathlib import Path


class AgentRegistry:
    def __init__(self, config_path="JARVIS_CORE/config/agents.json"):
        self.config_path = Path(config_path)

    def load_config(self):
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Agents config not found: {self.config_path}"
            )

        with open(self.config_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def get_enabled_agents(self):
        config = self.load_config()
        policy = config.get("policy", {})
        agents = config.get("agents", [])

        if policy.get("free_agents_only", True):
            agents = [
                agent for agent in agents
                if agent.get("cost") == "free"
            ]

        return [
            agent for agent in agents
            if agent.get("enabled") is True
        ]


if __name__ == "__main__":
    registry = AgentRegistry()
    agents = registry.get_enabled_agents()

    print("Enabled Free Agents:")
    for agent in agents:
        print(
            f"- {agent['name']} "
            f"({agent['provider']}) "
            f"[{agent['role']}]"
        )
