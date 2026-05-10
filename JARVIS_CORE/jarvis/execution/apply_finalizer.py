class ApplyFinalizer:
    def finalize(
        self,
        apply_session,
        patch_manifest,
        sandbox_simulation,
        sandbox_integrity,
        safety_receipt,
        audit_trail,
    ):
        issues = []

        if not apply_session:
            issues.append("Missing apply session.")

        if not patch_manifest:
            issues.append("Missing patch manifest.")

        if not sandbox_simulation:
            issues.append("Missing sandbox simulation.")

        if not sandbox_integrity or not sandbox_integrity.get("ok"):
            issues.append("Sandbox integrity verification failed.")

        if not safety_receipt:
            issues.append("Missing safety receipt.")

        if (
            safety_receipt
            and safety_receipt.get("original_files_modified") is not False
        ):
            issues.append("Original files modification status is unsafe.")

        if not audit_trail:
            issues.append("Missing audit trail event.")

        if issues:
            return {
                "status": "not_ready",
                "can_enable_real_apply": False,
                "issues": issues,
                "message": "Controlled apply finalization failed.",
            }

        return {
            "status": "finalized",
            "can_enable_real_apply": False,
            "issues": [],
            "message": (
                "Controlled apply simulation finalized successfully. "
                "Real apply remains disabled by policy."
            ),
        }
