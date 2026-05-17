import json
from datetime import datetime, timezone
from pathlib import Path


MEMORY_DIR = Path("JARVIS_CORE/runtime_memory")
DELEGATION_PATH = MEMORY_DIR / "agent_society_delegation.json"
CONSENSUS_PATH = MEMORY_DIR / "agent_society_consensus.json"


class AgentSocietyConsensus:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def load_delegation(self):
        if not DELEGATION_PATH.exists():
            return {}
        return json.loads(DELEGATION_PATH.read_text(encoding="utf-8"))

    def build_votes(self, task: str):
        text = (task or "").lower()

        risky_terms = ["delete", "drop", "destroy", "wipe", "force", "secret", "token"]
        has_risk = any(term in text for term in risky_terms)

        return {
            "validator_agent": {
                "vote": "approve" if not has_risk else "hold",
                "reason": "Validation path is bounded." if not has_risk else "Risk terms require stronger validation."
            },
            "reviewer_agent": {
                "vote": "approve" if not has_risk else "hold",
                "reason": "Workflow structure is reviewable." if not has_risk else "Manual review required before continuation."
            },
            "security_agent": {
                "vote": "approve" if not has_risk else "block",
                "reason": "No dangerous terms detected." if not has_risk else "Potentially destructive or sensitive operation detected."
            }
        }

    def decide(self, task: str):
        delegation = self.load_delegation()
        votes = self.build_votes(task)

        blocked = any(v["vote"] == "block" for v in votes.values())
        held = any(v["vote"] == "hold" for v in votes.values())

        if blocked:
            consensus_state = "blocked"
            execution_allowed = False
        elif held:
            consensus_state = "needs_human_review"
            execution_allowed = False
        else:
            consensus_state = "approved_for_planning_only"
            execution_allowed = False

        state = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "agent_society_consensus",
            "bounded": True,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "task": task,
            "delegation_state": delegation.get("workflow_state", "missing"),
            "consensus_state": consensus_state,
            "votes": votes,
            "approval_required": True,
            "execution_allowed": execution_allowed,
            "apply_allowed": False
        }

        CONSENSUS_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return state


if __name__ == "__main__":
    result = AgentSocietyConsensus().decide("implement safe dashboard patch")
    print(json.dumps(result, ensure_ascii=False, indent=2))
