from datetime import datetime, timezone


SAFETY_CONTRACT = {
    "bounded": True,
    "autonomous_apply": False,
    "deploy_allowed": False,
    "database_mutation_allowed": False,
    "destructive_execution_allowed": False,
    "human_approval_required_for_risky_actions": True,
    "voice_commands_bypass_governance": False,
}

DANGEROUS_TERMS = [
    "delete",
    "remove",
    "drop table",
    "truncate",
    "wipe",
    "format",
    "rm -rf",
    "deploy",
    "release to production",
    "database",
    "schema",
    "migration",
    "autonomous apply",
    "direct apply",
    "apply without approval",
    "external command",
    "powershell",
    "cmd.exe",
    "credential",
    "secret",
    "token",
]

RISKY_TERMS = [
    "modify",
    "edit",
    "change",
    "patch",
    "commit",
    "execute",
    "run",
    "route",
    "backend",
    "agent routing",
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def evaluate_voice_safety(recognized_text):
    text = (recognized_text or "").strip()
    lowered = text.lower()
    dangerous_hits = [term for term in DANGEROUS_TERMS if term in lowered]
    risky_hits = [term for term in RISKY_TERMS if term in lowered]

    if not text:
        return {
            "timestamp": _now(),
            "state": "blocked",
            "risk_level": "none",
            "allowed": False,
            "approval_required": False,
            "blocked_reason": "empty_voice_command",
            "matched_terms": [],
            "safety": SAFETY_CONTRACT,
        }

    if dangerous_hits:
        return {
            "timestamp": _now(),
            "state": "blocked",
            "risk_level": "critical",
            "allowed": False,
            "approval_required": True,
            "blocked_reason": "dangerous_voice_command_blocked",
            "matched_terms": dangerous_hits,
            "safety": SAFETY_CONTRACT,
        }

    if risky_hits:
        return {
            "timestamp": _now(),
            "state": "approval_required",
            "risk_level": "medium",
            "allowed": False,
            "approval_required": True,
            "blocked_reason": "risky_voice_command_requires_human_approval",
            "matched_terms": risky_hits,
            "safety": SAFETY_CONTRACT,
        }

    return {
        "timestamp": _now(),
        "state": "processing",
        "risk_level": "low",
        "allowed": True,
        "approval_required": False,
        "blocked_reason": None,
        "matched_terms": [],
        "safety": SAFETY_CONTRACT,
    }
