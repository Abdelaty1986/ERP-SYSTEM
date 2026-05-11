from dataclasses import dataclass, asdict
from datetime import datetime
import json


@dataclass
class RepairFinding:
    category: str
    severity: str
    message: str
    suggested_action: str


class AutonomousRepairLoop:
    def __init__(self):
        self.known_patterns = {
            "ModuleNotFoundError": ("missing_import_or_pythonpath", "medium", "راجع PYTHONPATH أو import path."),
            "SyntaxError": ("syntax_error", "high", "راجع آخر تعديل في الملف المذكور."),
            "IndentationError": ("indentation_error", "high", "راجع المسافات والـ indentation."),
            "AssertionError": ("test_assertion_failed", "medium", "راجع منطق الاختبار أو نتيجة الدالة."),
            "ImportError": ("import_error", "medium", "راجع اسم الموديول أو مكانه."),
            "NameError": ("undefined_name", "medium", "راجع المتغير أو الدالة غير المعرّفة."),
            "TypeError": ("type_error", "medium", "راجع أنواع البيانات أو عدد البراميترز."),
            "KeyError": ("missing_key", "medium", "راجع مفاتيح dict أو JSON."),
        }

    def analyze_failure(self, output):
        text = str(output or "")
        findings = []

        for pattern, (category, severity, action) in self.known_patterns.items():
            if pattern in text:
                findings.append(RepairFinding(
                    category=category,
                    severity=severity,
                    message=f"Detected {pattern} in runtime/test output.",
                    suggested_action=action,
                ))

        if not findings and text.strip():
            findings.append(RepairFinding(
                category="unknown_failure",
                severity="medium",
                message="Failure output detected but no known pattern matched.",
                suggested_action="راجع آخر stack trace وحدد الملف والسطر المتسبب في الخطأ.",
            ))

        if not text.strip():
            findings.append(RepairFinding(
                category="empty_failure_output",
                severity="low",
                message="No failure output was provided.",
                suggested_action="أعد تشغيل الاختبار مع طباعة stderr/stdout.",
            ))

        return findings

    def propose_repair_plan(self, task, failure_output):
        findings = self.analyze_failure(failure_output)

        severity_rank = {"low": 1, "medium": 2, "high": 3}
        highest = max(findings, key=lambda f: severity_rank.get(f.severity, 1))

        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "task": task,
            "status": "repair_plan_proposed",
            "safe_mode": True,
            "auto_apply": False,
            "highest_severity": highest.severity,
            "findings": [asdict(f) for f in findings],
            "next_steps": [
                "لا تطبق أي تعديل مباشر.",
                "حدد الملف والسطر من رسالة الخطأ.",
                "اقترح patch صغير ومعزول.",
                "اختبر patch في sandbox أو simulation.",
                "اعرض الإصلاح للمراجعة البشرية قبل التطبيق.",
            ],
        }

    def to_json(self, repair_plan):
        return json.dumps(repair_plan, ensure_ascii=False, indent=2)
