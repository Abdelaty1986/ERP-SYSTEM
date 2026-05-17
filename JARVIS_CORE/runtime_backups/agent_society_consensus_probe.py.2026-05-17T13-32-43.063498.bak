import json
from jarvis.runtime.agent_society_consensus import AgentSocietyConsensus


if __name__ == "__main__":
    runtime = AgentSocietyConsensus()

    safe_result = runtime.decide("implement safe dashboard patch")
    risky_result = runtime.decide("delete secrets and force apply patch")

    print(json.dumps({
        "runtime": "agent_society_consensus_probe",
        "bounded": True,
        "safe_consensus_state": safe_result["consensus_state"],
        "safe_apply_allowed": safe_result["apply_allowed"],
        "risky_consensus_state": risky_result["consensus_state"],
        "risky_apply_allowed": risky_result["apply_allowed"],
        "risky_security_vote": risky_result["votes"]["security_agent"]["vote"]
    }, ensure_ascii=False, indent=2))
