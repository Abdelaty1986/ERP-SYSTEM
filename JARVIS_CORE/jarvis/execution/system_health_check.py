from pathlib import Path


class ExecutionSystemHealthCheck:
    """
    Performs lightweight validation for the controlled apply system.
    """

    REQUIRED_FILES = [
        "apply_engine.py",
        "apply_contract.py",
        "apply_finalizer.py",
        "apply_session.py",
        "approval_manager.py",
        "audit_trail.py",
        "patch_manifest.py",
        "patch_materializer.py",
        "sandbox_apply_simulator.py",
        "sandbox_integrity_verifier.py",
    ]

    def __init__(self, root="."):
        self.execution_dir = (
            Path(root)
            / "JARVIS_CORE/jarvis/execution"
        )

    def run(self):
        missing = []

        for item in self.REQUIRED_FILES:
            target = self.execution_dir / item

            if not target.exists():
                missing.append(item)

        return {
            "status": (
                "healthy"
                if not missing
                else "degraded"
            ),
            "ok": not missing,
            "missing_files": missing,
            "checked_files": self.REQUIRED_FILES,
        }
