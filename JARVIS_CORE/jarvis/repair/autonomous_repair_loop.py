from dataclasses import dataclass, asdict
from datetime import datetime
import json
import uuid

from jarvis.health.runtime_health_monitor import RuntimeHealthMonitor
from jarvis.execution.runtime_timeline import RuntimeTimeline


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

    def analyze_health(self, health_snapshot=None):
        snapshot = health_snapshot or RuntimeHealthMonitor().overall_health()
        warnings = snapshot.get("warnings", [])
        findings = []

        action_map = {
            "queue_file_missing": "أنشئ queue file فارغ أو شغّل runtime worker لتهيئة queue.",
            "queue_has_bad_lines": "اعزل السطور التالفة من runtime_command_queue.jsonl قبل أي معالجة.",
            "queue_backlog_high": "شغّل worker tick تدريجيًا أو راجع سبب تراكم الأوامر.",
            "timeline_missing": "أنشئ timeline جديد عبر RuntimeTimeline قبل تشغيل telemetry.",
            "worker_state_missing": "أعد تهيئة RuntimeWorkerState بحالة idle آمنة.",
            "worker_state_corrupted": "استبدل worker state التالف بحالة idle بعد حفظ نسخة للفحص.",
            "runtime_health_monitor_failed": "راجع import path وملف runtime_health_monitor.py.",
        }

        severity_map = {
            "queue_has_bad_lines": "high",
            "worker_state_corrupted": "high",
            "runtime_health_monitor_failed": "high",
            "queue_backlog_high": "medium",
            "queue_file_missing": "medium",
            "timeline_missing": "medium",
            "worker_state_missing": "medium",
        }

        for warning in warnings:
            findings.append(RepairFinding(
                category=str(warning),
                severity=severity_map.get(str(warning), "low"),
                message=f"Runtime health warning detected: {warning}",
                suggested_action=action_map.get(str(warning), "راجع التحذير يدويًا قبل أي إصلاح."),
            ))

        if not findings:
            findings.append(RepairFinding(
                category="runtime_healthy",
                severity="low",
                message="Runtime health monitor reports no active warnings.",
                suggested_action="لا يوجد إصلاح مطلوب حاليًا. استمر في المراقبة.",
            ))

        return snapshot, findings

    def propose_health_repair_plan(self, health_snapshot=None):
        snapshot, findings = self.analyze_health(health_snapshot)

        severity_rank = {"low": 1, "medium": 2, "high": 3}
        highest = max(findings, key=lambda f: severity_rank.get(f.severity, 1))

        return {
            "repair_id": "repair-" + uuid.uuid4().hex[:12],
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "source": "runtime_health_monitor",
            "status": "repair_plan_proposed",
            "safe_mode": True,
            "auto_apply": False,
            "repair_mode": "simulation_only",
            "health_status": snapshot.get("status", "unknown"),
            "highest_severity": highest.severity,
            "findings": [asdict(f) for f in findings],
            "suggested_actions": [f.suggested_action for f in findings],
        }

    def simulate_health_repair(self, health_snapshot=None):
        plan = self.propose_health_repair_plan(health_snapshot)
        timeline = RuntimeTimeline()
        timeline.add_event(
            session_id=plan["repair_id"],
            stage="repair_simulation",
            agent_id="autonomous_repair_loop",
            status=plan["health_status"],
            message="Repair loop simulation generated safe repair plan",
            payload=plan,
        )
        return plan

    def to_json(self, repair_plan):
        return json.dumps(repair_plan, ensure_ascii=False, indent=2)
