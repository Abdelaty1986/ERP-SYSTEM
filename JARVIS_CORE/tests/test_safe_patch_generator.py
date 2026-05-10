from jarvis.execution.safe_patch_generator import SafePatchGenerator
from jarvis.execution.diff_renderer import DiffRenderer


def main():
    task = "راجع شاشة الفواتير واقترح تحسين آمن"
    expected_files = ["app.py", "templates/", "static/"]

    generator = SafePatchGenerator(project_root=".")
    patch_plan = generator.generate_patch_plan(
        task=task,
        expected_files=expected_files,
        inspections={}
    )

    renderer = DiffRenderer()
    print(renderer.render_patch_report(patch_plan))


if __name__ == "__main__":
    main()
