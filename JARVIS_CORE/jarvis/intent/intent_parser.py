import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

INTENT_LOG = Path("JARVIS_CORE/runtime_logs/intent_parsed_events.jsonl")

LOW_KEYWORDS = {
    "راجع", "فحص", "كشف", "استعرض", "شوف", "اعرض", "اقرأ",
    "review", "scan", "check", "show", "read", "display",
}
MEDIUM_KEYWORDS = {
    "اختبر", "جرب", "حلل", "عدل", "أعدل", "نظف",
    "test", "refactor", "analyze", "modify", "clean",
}
HIGH_KEYWORDS = {
    "أصلح", "صلح", "طبق", "نفذ", "ارفع", "ادفع", "غير",
    "fix", "apply", "deploy", "push", "change", "patch",
}

BLOCKED_PATTERNS = {
    "احذف", "امسح", "destroy", "delete",
    "ضرب", "أوقف", "stop", "kill",
    "سرقة", "steal", "hack",
    "تجاوز", "bypass",
    ".env", "secrets", "credentials", "token",
    "force-push", "force push",
    "rm -rf", "shutdown", "reboot",
}

def now() -> str:
    from datetime import datetime
    return datetime.utcnow().isoformat() + "Z"

def log_intent(raw: str, parsed: Dict[str, Any]) -> None:
    INTENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with INTENT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": now(),
            "raw": raw,
            "parsed": parsed,
        }, ensure_ascii=False) + "\n")


class ArabicIntentParser:

    def parse(self, text: str) -> Dict[str, Any]:
        raw = str(text or "").strip()
        if not raw:
            return {"intent": "unknown", "risk_level": "unknown", "error": "empty_input"}

        lower = raw.lower()

        for bp in BLOCKED_PATTERNS:
            if bp in lower:
                log_intent(raw, {"intent": "blocked", "reason": f"blocked_pattern:{bp}"})
                return {
                    "intent": "blocked",
                    "risk_level": "critical",
                    "error": f"Instruction blocked: contains '{bp}'",
                    "blocked_pattern": bp,
                }

        intent = self._detect_intent(raw, lower)
        risk = self._assess_risk(raw, lower, intent)
        targets = self._extract_targets(raw, lower)
        actions = self._propose_actions(intent, targets)
        validation = self._validation_steps(intent, targets)
        rollback = self._rollback_plan(intent, targets, risk)

        parsed = {
            "intent": intent,
            "risk_level": risk,
            "target_files": targets,
            "proposed_actions": actions,
            "validation_steps": validation,
            "rollback_plan": rollback,
            "original_text": raw,
        }
        log_intent(raw, parsed)
        return parsed

    def _detect_intent(self, raw: str, lower: str) -> str:
        # Direct English shortcut commands
        shortcut_map = {
            "system_review": "review",
            "scan_errors": "scan_errors",
            "run_tests": "run_tests",
            "report": "report",
            "improve": "improve",
        }
        if lower in shortcut_map:
            return shortcut_map[lower]

        if "refactor" in lower:
            return "refactor"

        # Check deploy/push BEFORE improve (تعديل overlaps)
        if any(w in raw for w in ["ارفع", "ادفع", "push", "نشر", "رفع"]):
            return "deploy"

        # Check debug BEFORE scan_errors (فشل overlaps)
        if any(w in raw for w in ["فشل", "عطل", "وقف"]):
            if any(w in raw for w in ["شوف", "سبب", "ليش", "لماذا", "تحليل"]):
                return "debug"
            return "debug"

        if any(w in raw for w in ["أخطاء", "مشاكل", "أعطال", "error", "bug"]):
            if any(w in raw for w in ["راجع", "شوف", "اعرض", "كشف", "اكتشف", "scan", "check"]):
                return "scan_errors"
            return "debug"

        if any(w in raw for w in ["راجع", "فحص", "استعرض", "review", "check"]):
            return "review"

        if any(w in raw for w in ["اختبار", "اختبر", "تجربة", "جرب", "test"]):
            return "test"

        # Check improve BEFORE fix (إصلاح / باتش overlaps)
        if any(w in raw for w in ["باتش", "patch", "تصحيح", "تعديل", "تحسين", "تطوير"]):
            return "improve"

        if any(w in raw for w in ["أصلح", "صلح", "fix", "إصلاح", "تصليح"]):
            return "fix"

        if any(w in raw for w in ["تقرير", "report", "حالة", "state"]):
            return "report"

        if any(w in raw for w in ["نظف", "تنظيف", "clean"]):
            return "clean"

        # Fallback: map to review if unknown
        return "review"

    def _assess_risk(self, raw: str, lower: str, intent: str) -> str:
        if any(w in raw for w in BLOCKED_PATTERNS):
            return "critical"

        if intent in ("fix", "deploy", "refactor"):
            if any(w in raw for w in ["app.py", "التطبيق", "الرئيسي", "core", "main"]):
                return "high"
            return "medium"

        if intent in ("improve", "patch"):
            return "high"

        if intent in ("test", "clean", "debug"):
            return "medium"

        if intent in ("review", "report", "scan_errors"):
            return "low"

        return "medium"

    def _extract_targets(self, raw: str, lower: str) -> List[str]:
        known_files = {
            "app.py", "system_health.py",
            "templates/jarvis/mobile_control_center.html",
        }
        found = []
        for kf in known_files:
            if kf in lower:
                found.append(kf)

        if "المشروع" in raw or "project" in lower:
            py_files = sorted(Path(".").glob("*.py"))
            found.extend(str(p) for p in py_files if str(p) not in found)

        if "ملف" in raw and not found:
            found.append("(infer from context)")

        if not found:
            found.append("project")
        return found[:5]

    def _propose_actions(self, intent: str, targets: List[str]) -> List[str]:
        base = {
            "review": ["Review project code", "Check runtime health", "List recent changes"],
            "scan_errors": ["Run py_compile on all Python files", "Collect syntax errors"],
            "test": ["Run available tests", "Collect results"],
            "fix": [f"Analyze {t}" for t in targets[:2]] + ["Generate patch"],
            "refactor": [f"Analyze structure of {t}" for t in targets[:2]] + ["Propose refactoring plan"],
            "improve": ["Generate improvement patch", "Preview changes"],
            "report": ["Collect system state", "Generate JSON report"],
            "debug": ["Inspect latest error logs", "Analyze failure context"],
            "clean": ["Identify unused files", "Propose cleanup"],
            "deploy": ["Verify build", "Stage changes"],
        }
        return base.get(intent, ["Analyze request", "Execute safe action"])

    def _validation_steps(self, intent: str, targets: List[str]) -> List[str]:
        steps = ["python -m py_compile on changed files"]
        if intent in ("review", "scan_errors", "debug"):
            return ["Verify output is valid"]
        if intent in ("fix", "refactor", "improve"):
            steps.append("Run py_compile on modified files")
            steps.append("Verify pre/post diff")
        if intent == "test":
            steps.append("Run pytest if available")
        if intent == "deploy":
            steps.append("Run full test suite")
            steps.append("Verify git status is clean")
        steps.append("Log results to execution journal")
        return steps

    def _rollback_plan(self, intent: str, targets: List[str], risk: str) -> List[str]:
        if risk == "low":
            return ["No rollback needed (read-only operation)"]
        plan = []
        for t in targets:
            if t and t != "project" and not t.startswith("("):
                plan.append(f"Backup {t} before modification")
        if risk == "high":
            plan.append("Create full checkpoint before apply")
            plan.append("Auto-rollback on validation failure")
        plan.append("Restore from backup if patch fails")
        return plan
