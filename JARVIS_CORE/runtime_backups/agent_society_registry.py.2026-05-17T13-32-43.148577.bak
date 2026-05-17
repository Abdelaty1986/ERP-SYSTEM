import json
from datetime import datetime, timezone
from pathlib import Path


MEMORY_DIR = Path("JARVIS_CORE/runtime_memory")
STATE_PATH = MEMORY_DIR / "agent_society_registry.json"


class AgentSocietyRegistry:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def build_registry(self):
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "agent_society_registry",
            "bounded": True,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "society_state": "initialized",
            "agents": {
                "planner_agent": {
                    "role": "planning",
                    "can_apply": False,
                    "risk_level": "low",
                    "description": "Breaks tasks into safe engineering steps."
                },
                "patch_agent": {
                    "role": "patch_generation",
                    "can_apply": False,
                    "risk_level": "medium",
                    "description": "Generates structured patch proposals only."
                },
                "reviewer_agent": {
                    "role": "review",
                    "can_apply": False,
                    "risk_level": "low",
                    "description": "Reviews proposed changes before approval."
                },
                "validator_agent": {
                    "role": "validation",
                    "can_apply": False,
                    "risk_level": "low",
                    "description": "Runs compile and runtime validation checks."
                },
                "rollback_agent": {
                    "role": "recovery",
                    "can_apply": False,
                    "risk_level": "medium",
                    "description": "Prepares rollback recommendations."
                },
                "memory_agent": {
                    "role": "memory",
                    "can_apply": False,
                    "risk_level": "low",
                    "description": "Records engineering outcomes and lessons."
                },
                "security_agent": {
                    "role": "governance",
                    "can_apply": False,
                    "risk_level": "high",
                    "description": "Blocks unsafe or destructive actions."
                }
            },
            "policy": {
                "human_approval_required": True,
                "auto_git_commit": False,
                "auto_git_push": False,
                "filesystem_scope": "bounded_project_runtime_only",
                "mutation_mode": "proposal_first"
            }
        }

    def write_state(self):
        state = self.build_registry()
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return state


if __name__ == "__main__":
    result = AgentSocietyRegistry().write_state()
    print(json.dumps(result, ensure_ascii=False, indent=2))
