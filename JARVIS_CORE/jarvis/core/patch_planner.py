class PatchPlanner:

    def create_patch_plan(self, task, plan):
        patch_plan = {
            "task": task,
            "patches": [],
            "requires_backup": False,
            "requires_tests": True,
            "requires_manual_approval": True,
            "risk_level": "medium"
        }

        for file_target in plan.get("expected_files", []):

            patch = {
                "target": file_target,
                "change_type": self._guess_change_type(
                    task,
                    file_target
                ),
                "risk": self._guess_risk(
                    task,
                    file_target
                )
            }

            patch_plan["patches"].append(patch)

        if any(
            patch["risk"] == "high"
            for patch in patch_plan["patches"]
        ):
            patch_plan["risk_level"] = "high"

        if any(
            "db" in patch["target"]
            or "migration" in patch["target"]
            for patch in patch_plan["patches"]
        ):
            patch_plan["requires_backup"] = True

        return patch_plan

    def _guess_change_type(self, task, target):

        lowered = task.lower()

        if target.endswith("/"):
            return "inspect_directory"

        if "واجهة" in lowered or "ui" in lowered:
            return "ui_update"

        if "قاعدة" in lowered or "database" in lowered:
            return "database_change"

        if "اختبار" in lowered or "test" in lowered:
            return "test_update"

        return "safe_modification"

    def _guess_risk(self, task, target):

        lowered = task.lower()

        if (
            "delete" in lowered
            or "حذف" in lowered
        ):
            return "high"

        if (
            "db" in target
            or "migration" in target
        ):
            return "high"

        if target.endswith("/"):
            return "low"

        return "medium"


if __name__ == "__main__":

    planner = PatchPlanner()

    sample_plan = {
        "expected_files": [
            "app.py",
            "templates/",
            "db.py"
        ]
    }

    patch_plan = planner.create_patch_plan(
        "راجع شاشة الفواتير واقترح تحسين آمن",
        sample_plan
    )

    print("Patch Plan")
    print("=" * 40)

    print(f"Risk Level: {patch_plan['risk_level']}")
    print(f"Requires Backup: {patch_plan['requires_backup']}")

    print("\nPatches:")

    for patch in patch_plan["patches"]:
        print(patch)
