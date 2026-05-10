from pathlib import Path
from datetime import datetime
import hashlib


class PatchMaterializer:
    """
    Converts safe patch proposals into staged diff artifacts
    inside the sandbox environment.
    """

    def __init__(self, root="."):
        self.root = Path(root)

        self.output_dir = (
            self.root
            / "JARVIS_CORE/jarvis/execution/sandbox/materialized_patches"
        )

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _timestamp(self):
        return datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    def _hash_text(self, text):
        return hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()

    def materialize_patch(self, patch_data):
        file_path = patch_data.get("file_path", "unknown")
        diff_preview = patch_data.get("diff_preview", "")

        safe_name = (
            file_path.replace("/", "_")
            .replace("\\", "_")
        )

        timestamp = self._timestamp()

        output_file = (
            self.output_dir
            / f"{safe_name}_{timestamp}.diff"
        )

        output_file.write_text(
            diff_preview,
            encoding="utf-8"
        )

        return {
            "file_path": file_path,
            "materialized_diff": str(output_file),
            "hash": self._hash_text(diff_preview),
            "timestamp": timestamp,
            "proposed_content": patch_data.get("proposed_content"),
        }
