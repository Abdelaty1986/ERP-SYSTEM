from pathlib import Path

from jarvis.execution.unified_diff_applier import UnifiedDiffApplier


class SandboxPatchApplier:
    """
    Applies proposed content to sandbox copies only.
    Original project files are never modified.
    """

    def __init__(self):
        self.applier = UnifiedDiffApplier()

    def _find_sandbox_file(self, simulation_result, file_path):
        target_name = Path(file_path).name

        for item in simulation_result.get("copied_files", []):
            simulation_copy = Path(item.get("simulation_copy", ""))

            if simulation_copy.name == target_name:
                return simulation_copy

        return None

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
            file_path = patch.get("file_path")
            proposed_content = patch.get("proposed_content")

            if not patch_file.exists():
                applied.append({
                    "file_path": file_path,
                    "status": "missing_patch_artifact",
                })
                continue

            if proposed_content is None:
                applied.append({
                    "file_path": file_path,
                    "patch_artifact": str(patch_file),
                    "status": "missing_proposed_content",
                })
                continue

            sandbox_file = self._find_sandbox_file(
                simulation_result,
                file_path,
            )

            if not sandbox_file:
                applied.append({
                    "file_path": file_path,
                    "patch_artifact": str(patch_file),
                    "status": "missing_sandbox_copy",
                })
                continue

            result = self.applier.apply_diff(
                sandbox_file=sandbox_file,
                proposed_content=proposed_content,
            )

            applied.append({
                "file_path": file_path,
                "patch_artifact": str(patch_file),
                "sandbox_file": str(sandbox_file),
                "status": result.get("status"),
                "ok": result.get("ok"),
            })

        ok = all(item.get("ok") for item in applied) if applied else True

        return {
            "status": "applied" if ok else "partial",
            "ok": ok,
            "simulation_dir": str(simulation_dir),
            "applied": applied,
            "original_files_modified": False,
            "message": (
                "Patch content applied to sandbox copies only. "
                "Original project files were not modified."
            ),
        }
