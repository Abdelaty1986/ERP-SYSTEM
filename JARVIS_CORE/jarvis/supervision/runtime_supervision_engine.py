from datetime import datetime

from jarvis.intelligence.erp_project_intelligence import (
    build_erp_project_snapshot,
)


class RuntimeSupervisionEngine:
    def __init__(self):
        self.snapshot = build_erp_project_snapshot()

    def _analyze_domains(self, relationships):
        domain_map = relationships.get("domain_map", {})
        findings = []

        for domain, state in domain_map.items():
            templates = state.get("templates", 0)
            modules = state.get("modules", 0)

            severity = "healthy"
            risk_score = 0

            if templates > 0 and modules == 0:
                severity = "warning"
                risk_score = 70

            elif modules > 0 and templates == 0:
                severity = "watch"
                risk_score = 50

            elif templates > modules * 4:
                severity = "watch"
                risk_score = 45

            findings.append({
                "domain": domain,
                "templates": templates,
                "modules": modules,
                "severity": severity,
                "risk_score": risk_score,
            })

        findings.sort(key=lambda item: item["risk_score"], reverse=True)

        return findings

    def _generate_supervision_notes(self, findings):
        notes = []

        for item in findings:
            domain = item["domain"]
            severity = item["severity"]

            if severity == "warning":
                notes.append(
                    f"{domain} may contain orphan templates without strong module ownership."
                )

            elif severity == "watch":
                notes.append(
                    f"{domain} shows possible structural imbalance and should be reviewed."
                )

            elif severity == "healthy":
                notes.append(
                    f"{domain} appears structurally balanced."
                )

        return notes[:20]

    def build_supervision_snapshot(self):
        relationships = self.snapshot.get("relationships", {})

        findings = self._analyze_domains(relationships)

        warning_count = len(
            [x for x in findings if x["severity"] == "warning"]
        )

        watch_count = len(
            [x for x in findings if x["severity"] == "watch"]
        )

        healthy_count = len(
            [x for x in findings if x["severity"] == "healthy"]
        )

        overall_state = "stable"

        if warning_count >= 2:
            overall_state = "attention-required"

        elif watch_count >= 3:
            overall_state = "monitoring"

        return {
            "available": True,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "overall_state": overall_state,
            "summary": {
                "warning_domains": warning_count,
                "watch_domains": watch_count,
                "healthy_domains": healthy_count,
                "total_domains": len(findings),
            },
            "domain_findings": findings,
            "supervision_notes": self._generate_supervision_notes(findings),
            "safe_mode": True,
            "bounded": True,
            "autonomy": "supervision_only",
        }


def build_runtime_supervision_snapshot():
    return RuntimeSupervisionEngine().build_supervision_snapshot()
