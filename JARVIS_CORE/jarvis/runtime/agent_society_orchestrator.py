import json
from datetime import datetime, timezone
from pathlib import Path

from jarvis.runtime.agent_society_router import AgentSocietyRouter
from jarvis.runtime.agent_society_delegation import AgentSocietyDelegation
from jarvis.runtime.agent_society_consensus import AgentSocietyConsensus


MEMORY_DIR = Path("JARVIS_CORE/runtime_memory")
ORCHESTRATOR_PATH = MEMORY_DIR / "agent_society_orchestrator.json"


class AgentSocietyOrchestrator:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

        self.router = AgentSocietyRouter()
        self.delegation = AgentSocietyDelegation()
        self.consensus = AgentSocietyConsensus()

    def execute(self, task: str):
        routing = self.router.route(task)
        delegation = self.delegation.delegate(task)
        consensus = self.consensus.decide(task)

        state = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "agent_society_orchestrator",
            "bounded": True,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "task": task,
            "selected_agent": routing.get("selected_agent"),
            "workflow_state": delegation.get("workflow_state"),
            "consensus_state": consensus.get("consensus_state"),
            "execution_allowed": False,
            "apply_allowed": False,
            "approval_required": True,
            "orchestration_state": "coordinated",
            "workflow_steps": len(delegation.get("workflow", []))
        }

        ORCHESTRATOR_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return state


if __name__ == "__main__":
    runtime = AgentSocietyOrchestrator()

    result = runtime.execute(
        "implement safe runtime dashboard patch"
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
