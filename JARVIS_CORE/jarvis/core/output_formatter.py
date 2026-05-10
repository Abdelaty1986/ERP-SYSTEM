class OutputFormatter:
    def format_report(self, report):
        lines = []

        lines.append("Jarvis Report")
        lines.append("=" * 40)
        lines.append(f"Project: {report.get('project_id')}")
        lines.append(f"Task: {report.get('task')}")
        lines.append("")

        plan = report.get("plan", {})
        lines.append("Plan")
        lines.append("-" * 40)
        lines.append(plan.get("project_summary", "No summary available."))

        lines.append("")
        lines.append("Expected Files")
        lines.append("-" * 40)
        for item in plan.get("expected_files", []):
            lines.append(f"- {item}")

        lines.append("")
        lines.append("Risks")
        lines.append("-" * 40)
        for risk in plan.get("risks", []):
            lines.append(f"- {risk}")

        lines.append("")
        lines.append("File Inspections")
        lines.append("-" * 40)
        for item in report.get("file_inspections", []):
            lines.append(
                f"- {item.get('file')}: {item.get('type')}"
            )

        decision = report.get("decision", {})
        lines.append("")
        lines.append("Decision")
        lines.append("-" * 40)
        lines.append(f"Status: {decision.get('status')}")
        lines.append(f"Can Apply: {decision.get('can_apply')}")
        lines.append(f"Reason: {decision.get('reason')}")

        return "\n".join(lines)


if __name__ == "__main__":
    sample = {
        "project_id": "ledgerx",
        "task": "راجع شاشة الفواتير",
        "plan": {
            "project_summary": "Sample project summary.",
            "expected_files": ["app.py", "templates/"],
            "risks": ["Invoice workflow risk."]
        },
        "file_inspections": [
            {"file": "app.py", "type": "file"},
            {"file": "templates/", "type": "directory"}
        ],
        "decision": {
            "status": "needs_human_review",
            "can_apply": False,
            "reason": "Approval required."
        }
    }

    print(OutputFormatter().format_report(sample))
