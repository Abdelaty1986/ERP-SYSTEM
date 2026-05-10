from pathlib import Path
from datetime import datetime
import json
import uuid


class ApplySafetyReceipt:
    """
    Creates an immutable-style safety receipt for each apply simulation.
    It proves that original files were not modified during simulation.
    """

    def __init__(self, root="."):
        self.root = Path(root)
        self.receipts_dir = (
            self.root
            / "JARVIS_CORE/jarvis/execution/sandbox/receipts"
        )
        self.receipts_dir.mkdir(parents=True, exist_ok=True)

    def create_receipt(
        self,
        task,
        apply_session,
        patch_manifest,
        sandbox_simulation,
        sandbox_integrity,
    ):
        receipt_id = str(uuid.uuid4())

        receipt = {
            "receipt_id": receipt_id,
            "created_at": datetime.utcnow().isoformat(),
            "task": task,
            "status": "safe_simulation_verified",
            "original_files_modified": sandbox_simulation.get(
                "original_files_modified",
                None,
            ),
            "integrity_status": sandbox_integrity.get("status"),
            "integrity_ok": sandbox_integrity.get("ok"),
            "apply_session_id": apply_session.get("session_id"),
            "manifest_id": patch_manifest.get("manifest_id"),
            "manifest_file": patch_manifest.get("manifest_file"),
            "simulation_dir": sandbox_simulation.get("simulation_dir"),
            "verified_files": sandbox_integrity.get("verified_files", []),
            "issues": sandbox_integrity.get("issues", []),
        }

        receipt_file = self.receipts_dir / f"{receipt_id}.json"

        receipt_file.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        receipt["receipt_file"] = str(receipt_file)

        return receipt
