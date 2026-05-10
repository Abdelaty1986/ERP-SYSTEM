from pathlib import Path
from datetime import datetime
import json
import uuid


class PatchManifest:
    """
    Stores a structured manifest for materialized patch artifacts.
    This is metadata only. It does not apply patches.
    """

    def __init__(self, root="."):
        self.root = Path(root)
        self.manifest_dir = (
            self.root
            / "JARVIS_CORE/jarvis/execution/sandbox/manifests"
        )
        self.manifest_dir.mkdir(parents=True, exist_ok=True)

    def create_manifest(self, task, materialized_patches, staged_targets):
        manifest_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()

        manifest = {
            "manifest_id": manifest_id,
            "created_at": timestamp,
            "task": task,
            "status": "created",
            "materialized_patches": materialized_patches,
            "staged_targets": staged_targets,
            "patch_count": len(materialized_patches or []),
            "staged_count": len(staged_targets or []),
        }

        manifest_file = self.manifest_dir / f"{manifest_id}.json"

        manifest_file.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        manifest["manifest_file"] = str(manifest_file)

        return manifest
