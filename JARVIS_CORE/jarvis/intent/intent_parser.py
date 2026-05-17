import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

INTENT_LOG = Path("JARVIS_CORE/runtime_logs/intent_parsed_events.jsonl")

# Only critical destructive protections — engineering tasks are always allowed
CRITICAL_BLOCKED_PATTERNS = {
    ".git/config", ".env", "secrets", "credentials", "token",
    "rm -rf /", "rm -rf ~", "rm -rf .", "rm -rf *",
    "shutdown", "reboot",
    "force-push", "force push --all",
}

# Multi-file engineering detection patterns
ENGINEERING_PATTERNS = {
    "multi_file": {"files", "ملفات", "عدة ملفات", "كل الملفات", "all", "multiple"},
    "refactor": {"refactor", "إعادة هيكلة", "أعد هيكلة", "إعادة تنظيم", "reorganize", "restructure"},
    "fix": {"fix", "bug", "أصلح", "صلح", "إصلاح", "تصليح", "خطأ", "غلط"},
    "import_fix": {"import", "استيراد", "module", "وحدة", "missing", "مفقود"},
    "restructure": {"restructure", "إعادة هيكلة", "أعد بناء", "rebuild"},
    "git_commit": {"commit", "git commit", "احفظ", "git add", "git push"},
    "railway_deploy": {"railway", "deploy", "انشر", "ارفع للسيرفر", "نشر على السيرفر"},
    "test": {"test", "اختبار", "اختبر", "تجربة", "جرب"},
    "review": {"review", "راجع", "فحص", "استعرض", "check", "كشف", "اقرأ", "read"},
    "scan_errors": {"scan", "error", "bug", "خطأ", "غلط", "أخطاء", "مشاكل"},
    "debug": {"debug", "حلل", "تحليل", "شوف", "فشل", "سبب"},
    "report": {"report", "تقرير", "حالة", "state"},
    "clean": {"clean", "نظف", "تنظيف"},
    "deploy": {"deploy", "انشر", "ارفع", "ادفع", "push"},
    "improve": {"improve", "حسن", "طور", "باتش", "patch", "تصحيح"},
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
            return {"intent": "review", "risk_level": "low", "target_files": [], "proposed_actions": ["No command provided"], "validation_steps": [], "rollback_plan": []}

        lower = raw.lower()

        # Block only absolutely destructive patterns
        for bp in CRITICAL_BLOCKED_PATTERNS:
            if bp in lower:
                log_intent(raw, {"intent": "blocked", "reason": f"critical_blocked:{bp}"})
                return {
                    "intent": "blocked",
                    "risk_level": "critical",
                    "error": f"Destructive instruction blocked: '{bp}'",
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

        # Check for multi-file / refactor intent FIRST
        if any(w in lower for w in ENGINEERING_PATTERNS["refactor"]):
            return "refactor"
        if any(w in lower for w in ENGINEERING_PATTERNS["restructure"]):
            return "refactor"
        if any(w in lower for w in ENGINEERING_PATTERNS["import_fix"]):
            return "fix"

        # Deploy/push FIRST (ارفع/ادفع should win over تعديل)
        if any(w in lower for w in ENGINEERING_PATTERNS["railway_deploy"]):
            return "deploy"
        if any(w in raw for w in ["ارفع", "ادفع", "push", "نشر", "رفع"]):
            return "deploy"

        # Apply patch
        if any(w in raw for w in ["طبق", "تطبيق", "طبق", "طبق التغييرات"]):
            return "apply"

        # Git commit prep
        if any(w in lower for w in ENGINEERING_PATTERNS["git_commit"]):
            return "git_commit"

        # Fix/improve — engineering commands win over analysis
        if any(w in raw for w in ["باتش", "patch", "تصحيح", "تحسين", "تطوير", "حسن", "طور"]):
            return "improve"
        if any(w in raw for w in ["أصلح", "صلح", "fix", "إصلاح", "تصليح"]):
            return "fix"
        # "تعديل" alone is improve, not fix
        if any(w in raw for w in ["تعديل", "تعديلات", "عدل", "أعدل"]):
            return "improve"

        # Debug (شوف + سبب = debug, even with خطأ)
        if any(w in raw for w in ["سبب", "ليش", "لماذا", "تحليل", "debug"]):
            return "debug"
        if any(w in raw for w in ["فشل", "عطل", "وقف"]):
            return "debug"

        # Errors (خطأ without fix intent)
        if any(w in raw for w in ["أخطاء", "مشاكل", "أعطال", "ثغرات", "ثغرة", "error", "bug", "خطأ"]):
            if any(w in raw for w in ["راجع", "شوف", "اعرض", "كشف", "اكتشف", "افتح", "scan", "check"]):
                return "scan_errors"
            return "debug"

        if any(w in raw for w in ["راجع", "فحص", "استعرض", "review", "check"]):
            return "review"

        if any(w in raw for w in ["اختبار", "اختبر", "تجربة", "جرب", "test"]):
            return "test"

        if any(w in raw for w in ["تقرير", "report", "حالة", "state"]):
            return "report"

        if any(w in raw for w in ["نظف", "تنظيف", "clean"]):
            return "clean"

        # Catch-all: route to planning pipeline — never reject
        return "review"

    def _assess_risk(self, raw: str, lower: str, intent: str) -> str:
        # Critical if blocked pattern
        for bp in CRITICAL_BLOCKED_PATTERNS:
            if bp in lower:
                return "critical"

        # HIGH risk: multi-file mutations, deploy, restructure
        multi_file = any(w in lower for w in ENGINEERING_PATTERNS["multi_file"])
        if intent in ("deploy", "git_commit", "apply") and multi_file:
            return "high"
        if intent in ("fix", "refactor") and multi_file:
            return "high"

        # MEDIUM risk: single file fix, refactor, improve, clean, apply
        if intent in ("fix", "refactor", "improve", "apply"):
            return "medium"
        if intent in ("test", "debug", "clean", "git_commit"):
            return "medium"
        if intent in ("deploy",):
            return "high"

        # LOW risk: review, scan, report
        if intent in ("review", "report", "scan_errors", "run_tests"):
            return "low"

        return "low"

    def _extract_targets(self, raw: str, lower: str) -> List[str]:
        known_files = {
            "app.py", "system_health.py",
            "templates/jarvis/mobile_control_center.html",
            "JARVIS_CORE/jarvis/intent/intent_parser.py",
            "JARVIS_CORE/jarvis/runtime/controlled_execution_engine.py",
            "JARVIS_CORE/jarvis/runtime/controlled_patch_manager.py",
            "JARVIS_CORE/jarvis/runtime/execution_mode_manager.py",
        }
        found = []
        for kf in known_files:
            if kf in lower:
                found.append(kf)

        # Detect Arabic file references
        if "app.py" in lower or "app" in lower.replace("طلب", ""):
            if "app.py" not in found:
                found.append("app.py")
        if "المشروع" in raw or "project" in lower:
            py_files = sorted(Path(".").glob("*.py"))
            found.extend(str(p) for p in py_files if str(p) not in found)
        if "ملف" in raw and not found:
            found.append("(multiple files)")
        if "كل" in raw or "all" in lower:
            found.append("(all project files)")

        if not found:
            found.append("project")
        return found[:5]

    def _propose_actions(self, intent: str, targets: List[str]) -> List[str]:
        base = {
            "review": ["Review project code", "Check runtime health", "List recent changes"],
            "scan_errors": ["Run py_compile on all Python files", "Collect syntax errors"],
            "run_tests": ["Run available tests", "Collect results"],
            "test": ["Run available tests", "Collect results"],
            "fix": ["Analyze errors", "Generate patch for " + (targets[0] if targets else "affected files"), "Apply fix", "Validate with py_compile"],
            "refactor": [f"Analyze structure of {t}" for t in targets[:2]] + ["Generate refactoring plan", "Apply changes", "Validate"],
            "improve": ["Generate improvement patch", "Preview changes", "Apply with approval"],
            "report": ["Collect system state", "Generate JSON report"],
            "debug": ["Inspect latest error logs", "Analyze failure context", "Propose fix"],
            "clean": ["Identify unused files", "Propose cleanup", "Execute with approval"],
            "deploy": ["Verify build", "Stage changes", "Run tests", "Deploy to Railway"],
            "apply": ["Backup target files", "Apply pending patch", "Validate with py_compile", "Rollback on failure"],
            "git_commit": ["Review git status", "Stage files", "Create commit", "Prepare push"],
        }
        return base.get(intent, ["Analyze request", "Route to planning pipeline"])

    def _validation_steps(self, intent: str, targets: List[str]) -> List[str]:
        steps = ["python -m py_compile on changed files"]
        if intent in ("review", "scan_errors", "debug"):
            return ["Verify output is valid"]
        if intent in ("fix", "refactor", "improve"):
            steps.append("Run py_compile on modified files")
            steps.append("Verify pre/post diff")
            steps.append("Check for import errors")
        if intent in ("test", "run_tests"):
            steps.append("Run pytest if available")
        if intent in ("apply",):
            steps.append("Backup files before modification")
            steps.append("py_compile after apply")
            steps.append("Auto-rollback on validation failure")
        if intent == "deploy":
            steps.append("Run full test suite")
            steps.append("Verify git status is clean")
            steps.append("Run Railway deploy dry-run")
        if intent == "git_commit":
            steps.append("Verify git diff")
            steps.append("Check commit message format")
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
            plan.append("Create full project checkpoint before apply")
            plan.append("Auto-rollback on validation failure")
        plan.append("Restore from backup if patch fails")
        if intent == "git_commit":
            plan.append("Revert to previous commit if needed")
        return plan
