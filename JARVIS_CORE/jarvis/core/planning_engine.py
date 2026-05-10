from jarvis.core.project_context_builder import ProjectContextBuilder


class PlanningEngine:
    def __init__(self, root_path="."):
        self.context_builder = ProjectContextBuilder(root_path)

    def create_plan(self, task):
        context = self.context_builder.build()
        task_lower = task.strip().lower()

        expected_files = self._guess_files(task_lower)
        risks = self._guess_risks(task_lower, context)

        return {
            "task": task,
            "project_summary": context["summary"],
            "expected_files": expected_files,
            "risks": risks,
            "steps": [
                "Understand the requested change.",
                "Inspect the related files before editing.",
                "Prepare a safe patch proposal.",
                "Run available tests.",
                "Ask for user approval before applying changes."
            ],
            "can_apply_directly": False
        }

    def _contains_any(self, text, keywords):
        return any(keyword in text for keyword in keywords)

    def _guess_files(self, task):
        files = []

        invoice_keywords = [
            "فاتورة",
            "فواتير",
            "invoice",
            "invoices",
            "sales"
        ]

        database_keywords = [
            "قاعدة",
            "database",
            "db",
            "sqlite",
            "migration"
        ]

        if self._contains_any(task, invoice_keywords):
            files.extend([
                "templates/",
                "static/",
                "app.py",
                "modules/",
                "tests/"
            ])

        if self._contains_any(task, database_keywords):
            files.extend([
                "db.py",
                "migrations.py",
                "tests/"
            ])

        if not files:
            files.append("Unknown until project files are inspected.")

        return sorted(set(files))

    def _guess_risks(self, task, context):
        risks = []

        if self._contains_any(task, ["حذف", "delete", "remove"]):
            risks.append("Deletion request detected. Requires strict approval.")

        if self._contains_any(task, ["قاعدة", "database", "db", "sqlite", "migration"]):
            risks.append("Database-related task. Migration safety required.")

        if self._contains_any(task, ["فاتورة", "فواتير", "invoice", "invoices", "sales"]):
            risks.append("Invoice workflow may affect accounting behavior.")

        risks.extend(context["risk_notes"])

        return risks


if __name__ == "__main__":
    planner = PlanningEngine(".")

    plan = planner.create_plan(
        "راجع شاشة الفواتير واقترح تحسين آمن"
    )

    print("Jarvis Plan")
    print("=" * 40)

    print(f"Task: {plan['task']}")
    print(f"Summary: {plan['project_summary']}")

    print("\nExpected Files:")
    for file in plan["expected_files"]:
        print(f"- {file}")

    print("\nRisks:")
    for risk in plan["risks"]:
        print(f"- {risk}")

    print("\nSteps:")
    for step in plan["steps"]:
        print(f"- {step}")
