import json
from datetime import datetime, timezone
from pathlib import Path


MEMORY_DIR = Path("JARVIS_CORE/runtime_memory")
REGISTRY_PATH = MEMORY_DIR / "agent_society_registry.json"
ROUTING_PATH = MEMORY_DIR / "agent_society_routing.json"


class AgentSocietyRouter:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def load_registry(self):
        if not REGISTRY_PATH.exists():
            return {}
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    def classify_task(self, task: str):
        text = (task or "").lower()

        if any(k in text for k in ["risk", "security", "danger", "unsafe", "permission", "governance"]):
            return "security_agent"

        if any(k in text for k in ["rollback", "recover", "restore", "failure", "failed"]):
            return "rollback_agent"

        if any(k in text for k in ["validate", "validation", "test", "compile", "checks"]):
            return "validator_agent"

        if any(k in text for k in ["review", "audit", "quality", "inspect"]):
            return "reviewer_agent"

        if any(k in text for k in ["patch", "code", "modify", "edit", "implement", "change"]):
            return "patch_agent"

        if any(k in text for k in ["memory", "learn", "record", "remember", "lesson"]):
            return "memory_agent"

        if any(k in text for k in ["plan", "strategy", "roadmap", "steps", "design"]):
            return "planner_agent"

        return "planner_agent"

    def route(self, task: str):
        registry = self.load_registry()
        agents = registry.get("agents", {})
        selected = self.classify_task(task)

        if selected not in agents:
            selected = "planner_agent"

        decision = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "agent_society_router",
            "bounded": True,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "task": task,
            "selected_agent": selected,
            "selected_role": agents.get(selected, {}).get("role"),
            "can_apply": agents.get(selected, {}).get("can_apply", False),
            "risk_level": agents.get(selected, {}).get("risk_level", "unknown"),
            "routing_state": "routed",
            "approval_required": True,
            "execution_allowed": False
        }

        ROUTING_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
        return decision


if __name__ == "__main__":
    sample_task = "plan a safe patch and validate it"
    result = AgentSocietyRouter().route(sample_task)
    print(json.dumps(result, ensure_ascii=False, indent=2))
