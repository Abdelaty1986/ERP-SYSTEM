
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

from jarvis.runtime.runtime_intent_pipeline import classify_intent

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_MEMORY = ROOT / "runtime_memory"
DECISION_LOG = RUNTIME_MEMORY / "runtime_governance_decisions.json"

BOUNDED = True
DANGEROUS_AUTONOMOUS_APPLY = False

DANGEROUS_TERMS = [
    "delete", "remove all", "drop table", "format", "wipe",
    "rm -rf", "kill", "shutdown", "commit secret", "push token",
    "autonomous apply", "direct apply", "dangerous apply"
]

MEDIUM_RISK_TERMS = [
    "edit", "patch", "modify", "commit", "run", "execute",
    "deploy", "push", "merge"
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load_decisions():
    if not DECISION_LOG.exists():
        return []
    try:
        return json.loads(DECISION_LOG.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_decisions(decisions):
    RUNTIME_MEMORY.mkdir(parents=True, exist_ok=True)
    DECISION_LOG.write_text(
        json.dumps(decisions, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def assess_risk(message: str):
    text = (message or "").lower()

    if any(term in text for term in DANGEROUS_TERMS):
        return {
            "risk_level": "high",
            "approval_gate": "blocked",
            "confidence": 0.95,
            "reason": "dangerous_term_detected"
        }

    if any(term in text for term in MEDIUM_RISK_TERMS):
        return {
            "risk_level": "medium",
            "approval_gate": "human_required",
            "confidence": 0.78,
            "reason": "mutation_or_execution_term_detected"
        }

    return {
        "risk_level": "low",
        "approval_gate": "monitor_only",
        "confidence": 0.86,
        "reason": "safe_monitoring_request"
    }


def create_governance_decision(message: str):
    intent = classify_intent(message)
    risk = assess_risk(message)

    decision = {
        "decision_id": str(uuid.uuid4()),
        "timestamp": _now(),
        "runtime": "runtime_governance_decision",
        "message": message,
        "classified_intent": intent,
        "risk_level": risk["risk_level"],
        "approval_gate": risk["approval_gate"],
        "confidence": risk["confidence"],
        "reason": risk["reason"],
        "execution_mode": "simulation_only",
        "execution_allowed": False,
        "bounded": BOUNDED,
        "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
        "governance": {
            "rollback_safe": True,
            "staged_progression": True,
            "human_approval_required": risk["approval_gate"] != "monitor_only",
            "runtime_monitored": True,
            "autonomous_apply_allowed": False
        }
    }

    decisions = _load_decisions()
    decisions.append(decision)
    _save_decisions(decisions)

    return decision


def get_governance_decisions(limit=10):
    decisions = _load_decisions()
    return {
        "runtime": "runtime_governance_decision",
        "bounded": BOUNDED,
        "dangerous_autonomous_apply": DANGEROUS_AUTONOMOUS_APPLY,
        "decision_count": len(decisions),
        "decisions": decisions[-limit:]
    }
