from dataclasses import dataclass, asdict
from datetime import datetime
import json


@dataclass
class AgentOpinion:
    agent_id: str
    decision: str
    confidence: float
    risk_level: str
    notes: str = ""


class MultiAgentConsensusEngine:
    SAFE_DECISIONS = {"approve", "safe", "proceed"}
    BLOCK_DECISIONS = {"reject", "block", "unsafe"}

    def normalize_decision(self, decision):
        return str(decision or "").strip().lower()

    def risk_weight(self, risk_level):
        risk = str(risk_level or "").strip().lower()
        if risk == "high":
            return 3
        if risk == "medium":
            return 2
        if risk == "low":
            return 1
        return 2

    def evaluate(self, opinions):
        normalized = []
        safe_votes = 0
        block_votes = 0
        total_confidence = 0.0
        max_risk = "low"
        max_risk_weight = 1

        for opinion in opinions:
            if isinstance(opinion, dict):
                opinion = AgentOpinion(**opinion)

            decision = self.normalize_decision(opinion.decision)
            confidence = float(opinion.confidence or 0)
            risk = str(opinion.risk_level or "medium").lower()
            risk_w = self.risk_weight(risk)

            if decision in self.SAFE_DECISIONS:
                safe_votes += 1
            if decision in self.BLOCK_DECISIONS:
                block_votes += 1

            if risk_w > max_risk_weight:
                max_risk_weight = risk_w
                max_risk = risk

            total_confidence += confidence

            normalized.append(asdict(opinion))

        total = len(normalized)
        avg_confidence = round(total_confidence / total, 3) if total else 0

        disagreement = safe_votes > 0 and block_votes > 0

        if total == 0:
            final_decision = "blocked"
            reason = "no_agent_opinions"
        elif block_votes > 0:
            final_decision = "blocked"
            reason = "one_or_more_agents_blocked"
        elif disagreement:
            final_decision = "blocked"
            reason = "agent_disagreement_detected"
        elif max_risk_weight >= 3:
            final_decision = "blocked"
            reason = "high_risk_detected"
        elif avg_confidence < 0.65:
            final_decision = "needs_human_review"
            reason = "low_average_confidence"
        else:
            final_decision = "approved"
            reason = "consensus_approved"

        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "final_decision": final_decision,
            "reason": reason,
            "safe_votes": safe_votes,
            "block_votes": block_votes,
            "total_agents": total,
            "avg_confidence": avg_confidence,
            "max_risk": max_risk,
            "disagreement": disagreement,
            "opinions": normalized,
        }

    def to_json(self, result):
        return json.dumps(result, ensure_ascii=False, indent=2)
