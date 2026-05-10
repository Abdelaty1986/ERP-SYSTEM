from jarvis.core.project_scanner import ProjectScanner


class ProjectContextBuilder:
    def __init__(self, root_path="."):
        self.scanner = ProjectScanner(root_path)

    def build(self):
        scan = self.scanner.scan()

        context = {
            "summary": self._build_summary(scan),
            "stack": scan["detected_stack"],
            "important_files": scan["important_files"],
            "top_level_dirs": scan["top_level_dirs"],
            "risk_notes": self._build_risk_notes(scan)
        }

        return context

    def _build_summary(self, scan):
        stack = ", ".join(scan["detected_stack"])

        return (
            f"This project contains approximately "
            f"{scan['total_files']} files. "
            f"Detected stack: {stack}."
        )

    def _build_risk_notes(self, scan):
        notes = []

        important = scan["important_files"]

        if "app.py" in important:
            notes.append(
                "app.py detected as possible main application entry point."
            )

        if "db.py" in important:
            notes.append(
                "Database layer detected."
            )

        if "migrations.py" in important:
            notes.append(
                "Migration system detected. "
                "Database changes require caution."
            )

        if "tests" in scan["top_level_dirs"]:
            notes.append(
                "Tests directory detected."
            )

        return notes


if __name__ == "__main__":
    builder = ProjectContextBuilder(".")

    context = builder.build()

    print("Project Context")
    print("=" * 40)

    print(context["summary"])

    print("\nRisk Notes:")
    for note in context["risk_notes"]:
        print(f"- {note}")
