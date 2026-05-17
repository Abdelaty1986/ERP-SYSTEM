import json
from datetime import datetime, timezone
from pathlib import Path


MEMORY_DIR = Path("JARVIS_CORE/runtime_memory")
DELEGATION_PATH = MEMORY_DIR / "agent_society_delegation.json"


class AgentSocietyDelegation:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def build_workflow(self, task: str):
        text = (task or "").lower()

        workflow = []

        workflow.append({
            "step": 1,
            "agent": "planner_agent",
            "action": "analyze_task"
        })

        if any(k in text for k in ["patch", "implement", "modify", "edit"]):
            workflow.append({
                "step": 2,
                "agent": "patch_agent",
                "action": "generate_patch"
            })

        workflow.append({
            "step": 3,
            "agent": "validator_agent",
            "action": "run_validation"
        })

        workflow.append({
            "step": 4,
            "agent": "reviewer_agent",
            "action": "review_results"
        })

        workflow.append({
            "step": 5,
            "agent": "security_agent",
            "action": "governance_check"
        })

        workflow.append({
            "step": 6,
            "agent": "memory_agent",
            "action": "record_outcome"
        })

        return workflow

    def delegate(self, task: str):
        workflow = self.build_workflow(task)

        state = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "agent_society_delegation",
            "bounded": True,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "task": task,
            "workflow_state": "delegated",
            "approval_required": True,
            "execution_allowed": False,
            "workflow": workflow
        }

        DELEGATION_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return state


if __name__ == "__main__":
    task = "implement safe dashboard patch"
    result = AgentSocietyDelegation().delegate(task)

    print(json.dumps(result, ensure_ascii=False, indent=2))
