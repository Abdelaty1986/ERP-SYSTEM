from pathlib import Path
import hashlib


class SandboxIntegrityVerifier:
    """
    Verifies sandbox simulation integrity.
    It confirms copied files exist and hashes can be calculated.
    It never modifies original project files.
    """

    def _hash_file(self, file_path):
        path = Path(file_path)

        if not path.exists() or not path.is_file():
            return None

        sha = hashlib.sha256()

        with open(path, "rb") as f:
            while chunk := f.read(8192):
                sha.update(chunk)

        return sha.hexdigest()

    def verify(self, simulation_result, mode="pre_apply"):
        if not simulation_result:
            return {
                "status": "missing_simulation",
                "ok": False,
                "mode": mode,
                "issues": ["No sandbox simulation result found."],
            }

        issues = []
        verified_files = []

        for item in simulation_result.get("copied_files", []):
            copied_path = item.get("simulation_copy")
            expected_hash = item.get("hash")
            actual_hash = self._hash_file(copied_path)

            if not actual_hash:
                issues.append(f"Missing simulation copy: {copied_path}")
                continue

            if mode == "pre_apply" and expected_hash != actual_hash:
                issues.append(f"Hash mismatch before apply: {copied_path}")
                continue

            verified_files.append({
                "file": copied_path,
                "original_hash": expected_hash,
                "current_hash": actual_hash,
                "status": "verified",
            })

        if issues:
            return {
                "status": "failed",
                "ok": False,
                "mode": mode,
                "issues": issues,
                "verified_files": verified_files,
                "original_files_modified": False,
            }

        return {
            "status": "passed",
            "ok": True,
            "mode": mode,
            "issues": [],
            "verified_files": verified_files,
            "original_files_modified": False,
        }
