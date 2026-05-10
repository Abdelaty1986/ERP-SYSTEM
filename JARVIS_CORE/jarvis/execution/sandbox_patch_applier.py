from pathlib import Path


class SandboxPatchApplier:
    """
    Simulates applying patch artifacts inside sandbox only.
    This does not modify original project files.

    Current phase records intended application only.
    Real line-level patch application will be enabled later.
    """

    def apply_to_sandbox(self, simulation_result, materialized_patches):
        simulation_dir = Path(
            simulation_result.get("simulation_dir", "")
        )

        if not simulation_dir.exists():
            return {
                "status": "blocked",
                "ok": False,
                "reason": "Simulation directory does not exist.",
                "applied": [],
            }

        applied = []

        for patch in materialized_patches or []:
            patch_file = Path(patch.get("materialized_diff", ""))

            if not patch_file.exists():
                applied.append({
                    "file_path": patch.get("file_path"),
                    "status": "missing_patch_artifact",
                })
                continue

            applied.append({
                "file_path": patch.get("file_path"),
                "patch_artifact": str(patch_file),
                "status": "sandbox_apply_recorded",
            })

        return {
            "status": "recorded",
            "ok": True,
            "simulation_dir": str(simulation_dir),
            "applied": applied,
            "original_files_modified": False,
            "message": (
                "Patch application recorded in sandbox only. "
                "Original project files were not modified."
            ),
        }
