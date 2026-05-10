class RuntimeReportFormatter:
    """
    Centralized formatter for Jarvis execution runtime reports.
    """

    def format(self, report: dict) -> str:
        lines = []

        lines.append("Jarvis Execution Report")
        lines.append("=" * 40)

        self._task(lines, report)
        self._expected_files(lines, report)
        self._inspections(lines, report)
        self._decision(lines, report)
        self._patches(lines, report)
        self._target_resolution(lines, report)
        self._validation(lines, report)
        self._approval(lines, report)
        self._tests(lines, report)
        self._rollback(lines, report)
        self._apply(lines, report)
        self._contract(lines, report)
        self._state(lines, report)

        return "\n".join(lines)

    def _task(self, lines, report):
        lines.append(f"Task: {report.get('task')}")

    def _expected_files(self, lines, report):
        lines.append("\nExpected Files:")

        for item in report.get("plan", {}).get("expected_files", []):
            lines.append(f"- {item}")

    def _inspections(self, lines, report):
        lines.append("\nFile Inspections:")

        for item in report.get("file_inspections", []):
            lines.append(f"- {item['file']}: {item['type']}")

    def _decision(self, lines, report):
        lines.append("\nDecision:")
        lines.append(
            report.get("decision", {}).get("status", "unknown")
        )

    def _patches(self, lines, report):
        lines.append("\nSafe Patch Proposal:")
        lines.append("-" * 40)

        for item in report.get("safe_patch_plan", {}).get("patches", []):
            lines.append(
                f"- {item['file_path']} | "
                f"{item['change_type']} | "
                f"{item['risk_level']}"
            )

    def _target_resolution(self, lines, report):
        resolution = report.get("safe_patch_plan", {}).get(
            "target_resolution",
            {}
        )

        if not resolution:
            return

        lines.append("\nTarget Resolution:")
        lines.append("-" * 40)
        lines.append(f"Status: {resolution.get('status')}")
        lines.append(
            f"Resolved: {resolution.get('resolved_count')} | "
            f"Skipped: {resolution.get('skipped_count')}"
        )

        resolved_targets = resolution.get("resolved_targets", [])

        if resolved_targets:
            lines.append("Resolved Targets:")

            for item in resolved_targets:
                lines.append(f"- {item}")

        skipped_targets = resolution.get("skipped_targets", [])

        if skipped_targets:
            lines.append("Skipped Original Targets:")

            for item in skipped_targets:
                lines.append(
                    f"- {item.get('target')} | "
                    f"{item.get('reason')}"
                )

    def _validation(self, lines, report):
        validation = report.get("patch_validation", {})

        lines.append("\nPatch Validation:")
        lines.append("-" * 40)
        lines.append(validation.get("status", "unknown"))
        lines.append(validation.get("summary", ""))

    def _approval(self, lines, report):
        approval = report.get("approval_decision", {})

        lines.append("\nApproval Status:")
        lines.append("-" * 40)
        lines.append(approval.get("status", "unknown"))
        lines.append(approval.get("message", ""))

    def _tests(self, lines, report):
        discovery = report.get("test_discovery", {})
        execution = report.get("test_execution", {})

        lines.append("\nTest Discovery:")
        lines.append("-" * 40)
        lines.append(discovery.get("status", "unknown"))

        for cmd in discovery.get("commands", []):
            lines.append(
                f"- {cmd['name']}: {' '.join(cmd['command'])}"
            )

        lines.append("\nTest Execution:")
        lines.append("-" * 40)
        lines.append(execution.get("status", "unknown"))
        lines.append(execution.get("summary", ""))

    def _rollback(self, lines, report):
        ephemeral_branch = report.get("ephemeral_branch", {})

        if ephemeral_branch:
            lines.append("\nEphemeral Execution Branch:")
            lines.append("-" * 40)
            lines.append(f"Status: {ephemeral_branch.get('status')}")
            lines.append(f"OK: {ephemeral_branch.get('ok')}")
            lines.append(f"Branch: {ephemeral_branch.get('branch')}")
            lines.append(f"Base Branch: {ephemeral_branch.get('base_branch', '')}")
            lines.append(f"Reason: {ephemeral_branch.get('reason')}")

        branch_restore = report.get("branch_restore", {})

        if branch_restore:
            lines.append("\nBranch Restore:")
            lines.append("-" * 40)
            lines.append(f"Status: {branch_restore.get('status')}")
            lines.append(f"OK: {branch_restore.get('ok')}")
            lines.append(f"Base Branch: {branch_restore.get('base_branch', '')}")
            lines.append(f"Reason: {branch_restore.get('reason')}")

        rollback = report.get("rollback_checkpoint", {})

        lines.append("\nRollback Checkpoint:")
        lines.append("-" * 40)
        lines.append(rollback.get("status", "unknown"))

        if rollback.get("commit"):
            lines.append(rollback["commit"])

    def _apply(self, lines, report):
        apply_readiness = report.get("apply_readiness", {})

        lines.append("\nApply Readiness:")
        lines.append("-" * 40)
        lines.append(
            apply_readiness.get("status", "unknown")
        )

        lines.append(
            apply_readiness.get("message")
            or apply_readiness.get("reason", "")
        )

        apply_session = apply_readiness.get("apply_session", {})

        if apply_session:
            lines.append("\nApply Session:")
            lines.append("-" * 40)

            lines.append(
                f"Session ID: "
                f"{apply_session.get('session_id', 'unknown')}"
            )

            lines.append(
                f"Status: "
                f"{apply_session.get('status', 'unknown')}"
            )

            lines.append(
                f"Validation Passed: "
                f"{apply_session.get('validation_passed')}"
            )

            lines.append(
                f"Approval Received: "
                f"{apply_session.get('approval_received')}"
            )

            lines.append(
                f"Tests Passed: "
                f"{apply_session.get('tests_passed')}"
            )

            staged_files = apply_session.get("staged_files", [])

            if staged_files:
                lines.append("\nStaged Files:")

                for item in staged_files:
                    lines.append(
                        f"- {item.get('source')} "
                        f"-> {item.get('staged')}"
                    )

            quality_gate = apply_readiness.get("diff_quality_gate", {})

            if quality_gate:
                lines.append("\nDiff Quality Gate:")
                lines.append(f"- Status: {quality_gate.get('status')}")
                lines.append(f"- Approved: {quality_gate.get('approved_count')}")
                lines.append(f"- Blocked: {quality_gate.get('blocked_count')}")
                lines.append(f"- Message: {quality_gate.get('message')}")

                results = quality_gate.get("results", [])

                if results:
                    lines.append("- Details:")

                    for item in results:
                        issues = item.get("issues", [])
                        issue_text = "; ".join(issues) if issues else "no issues"

                        lines.append(
                            f"  - {item.get('file_path')} | "
                            f"{item.get('status')} | "
                            f"risk={item.get('risk_level')} | "
                            f"+{item.get('added_lines')} "
                            f"-{item.get('removed_lines')} | "
                            f"{issue_text}"
                        )

            materialized_patches = apply_readiness.get("materialized_patches", [])

            if materialized_patches:
                lines.append("\nMaterialized Patches:")

                for item in materialized_patches:
                    lines.append(
                        f"- {item.get('file_path')} "
                        f"-> {item.get('materialized_diff')} "
                        f"| hash: {item.get('hash')}"
                    )

            simulation = apply_readiness.get("sandbox_apply_simulation", {})

            if simulation:
                lines.append("\nSandbox Apply Simulation:")
                lines.append(f"- Status: {simulation.get('status')}")
                lines.append(f"- Simulation Dir: {simulation.get('simulation_dir')}")
                lines.append(
                    f"- Original Files Modified: "
                    f"{simulation.get('original_files_modified')}"
                )

                copied_files = simulation.get("copied_files", [])

                if copied_files:
                    lines.append("- Copied Files:")

                    for item in copied_files:
                        lines.append(
                            f"  - {item.get('source')} "
                            f"-> {item.get('simulation_copy')}"
                        )

            integrity = apply_readiness.get("sandbox_integrity", {})

            if integrity:
                lines.append("\nSandbox Integrity:")
                lines.append(f"- Status: {integrity.get('status')}")
                lines.append(f"- OK: {integrity.get('ok')}")

                verified_files = integrity.get("verified_files", [])

                if verified_files:
                    lines.append("- Verified Files:")

                    for item in verified_files:
                        lines.append(
                            f"  - {item.get('file')} | "
                            f"{item.get('status')}"
                        )

                issues = integrity.get("issues", [])

                if issues:
                    lines.append("- Issues:")

                    for item in issues:
                        lines.append(f"  - {item}")

            sandbox_patch_apply = apply_readiness.get("sandbox_patch_apply", {})

            if sandbox_patch_apply:
                lines.append("\nSandbox Patch Apply:")
                lines.append(f"- Status: {sandbox_patch_apply.get('status')}")
                lines.append(f"- OK: {sandbox_patch_apply.get('ok')}")
                lines.append(
                    f"- Original Files Modified: "
                    f"{sandbox_patch_apply.get('original_files_modified')}"
                )

                applied = sandbox_patch_apply.get("applied", [])

                if applied:
                    lines.append("- Applied Patch Records:")

                    for item in applied:
                        lines.append(
                            f"  - {item.get('file_path')} | "
                            f"{item.get('status')}"
                        )

            post_apply_tests = apply_readiness.get("post_apply_tests", {})

            if post_apply_tests:
                lines.append("\nPost Apply Sandbox Tests:")
                lines.append(f"- Status: {post_apply_tests.get('status')}")
                lines.append(f"- Checked: {post_apply_tests.get('checked_count')}")
                lines.append(f"- Failed: {post_apply_tests.get('failed_count')}")

                for item in post_apply_tests.get("results", []):
                    lines.append(
                        f"  - {item.get('file')} | "
                        f"{item.get('status')}"
                    )

            receipt = apply_readiness.get("apply_safety_receipt", {})

            if receipt:
                lines.append("\nApply Safety Receipt:")
                lines.append(f"- Receipt ID: {receipt.get('receipt_id')}")
                lines.append(f"- Status: {receipt.get('status')}")
                lines.append(f"- Integrity OK: {receipt.get('integrity_ok')}")
                lines.append(
                    f"- Original Files Modified: "
                    f"{receipt.get('original_files_modified')}"
                )
                lines.append(f"- Receipt File: {receipt.get('receipt_file')}")
                lines.append(
                    f"- Signature Algorithm: "
                    f"{receipt.get('signature_algorithm')}"
                )
                lines.append(
                    f"- Signed At: "
                    f"{receipt.get('signed_at')}"
                )

                signature = receipt.get("signature", "")

                if signature:
                    lines.append(
                        f"- Signature: {signature[:24]}..."
                    )

            audit = apply_readiness.get("audit_trail", {})

            if audit:
                lines.append("\nAudit Trail:")
                lines.append(f"- Status: {audit.get('status')}")
                lines.append(f"- Event Type: {audit.get('event_type')}")
                lines.append(f"- Audit File: {audit.get('audit_file')}")

            finalization = apply_readiness.get("apply_finalization", {})

            if finalization:
                lines.append("\nApply Finalization:")
                lines.append(f"- Status: {finalization.get('status')}")
                lines.append(
                    f"- Can Enable Real Apply: "
                    f"{finalization.get('can_enable_real_apply')}"
                )
                lines.append(f"- Message: {finalization.get('message')}")

            system_health = apply_readiness.get("system_health", {})

            if system_health:
                lines.append("\nExecution System Health:")
                lines.append(
                    f"- Status: {system_health.get('status')}"
                )
                lines.append(
                    f"- OK: {system_health.get('ok')}"
                )

            real_apply = apply_readiness.get("real_apply_switch", {})

            if real_apply:
                lines.append("\nReal Apply Switch:")
                lines.append(f"- Mode: {real_apply.get('mode')}")
                lines.append(f"- Enabled: {real_apply.get('enabled')}")
                lines.append(
                    f"- Can Apply Real Files: "
                    f"{real_apply.get('can_apply_real_files')}"
                )
                lines.append(f"- Reason: {real_apply.get('reason')}")

            real_apply_policy = report.get("real_apply_policy", {})

            if real_apply_policy:
                lines.append("\nReal Apply Policy:")
                lines.append("-" * 40)
                lines.append(f"Status: {real_apply_policy.get('status')}")
                lines.append(f"OK: {real_apply_policy.get('ok')}")
                lines.append(f"Mode: {real_apply_policy.get('mode')}")
                lines.append(f"Branch: {real_apply_policy.get('branch')}")
                lines.append(f"Reason: {real_apply_policy.get('reason')}")
                lines.append(
                    f"Can Apply Real Files: "
                    f"{real_apply_policy.get('can_apply_real_files')}"
                )

            real_apply_applier = report.get("real_apply_applier", {})

            if real_apply_applier:
                lines.append("\nReal Apply Applier:")
                lines.append("-" * 40)
                lines.append(f"Status: {real_apply_applier.get('status')}")
                lines.append(f"OK: {real_apply_applier.get('ok')}")
                lines.append(f"Reason: {real_apply_applier.get('reason', '')}")

                applied_files = real_apply_applier.get("applied_files", [])
                failed_files = real_apply_applier.get("failed_files", [])

                lines.append(f"Applied Files: {len(applied_files)}")
                lines.append(f"Failed Files: {len(failed_files)}")

                for item in applied_files:
                    lines.append(f"- {item.get('target')} | {item.get('status')}")

                for item in failed_files:
                    lines.append(f"- {item.get('target')} | {item.get('reason')}")

            rollback_recovery = report.get("rollback_recovery", {})

            if rollback_recovery:
                lines.append("\nRollback Recovery:")
                lines.append("-" * 40)
                lines.append(f"Status: {rollback_recovery.get('status')}")
                lines.append(f"Triggered: {rollback_recovery.get('triggered')}")
                lines.append(f"Reason: {rollback_recovery.get('reason', '')}")

                restored_files = rollback_recovery.get("restored_files", [])
                failed_files = rollback_recovery.get("failed_files", [])

                lines.append(f"Restored Files: {len(restored_files)}")
                lines.append(f"Failed Files: {len(failed_files)}")

                for item in restored_files:
                    lines.append(f"- {item}")

                for item in failed_files:
                    lines.append(
                        f"- {item.get('file')} | {item.get('error')}"
                    )

            execution_tag = report.get("execution_tag", {})

            if execution_tag:
                lines.append("\nExecution Git Tag:")
                lines.append("-" * 40)
                lines.append(f"Status: {execution_tag.get('status')}")
                lines.append(f"OK: {execution_tag.get('ok')}")
                lines.append(f"Reason: {execution_tag.get('reason')}")
                lines.append(f"Tag: {execution_tag.get('tag')}")
                lines.append(f"Commit: {execution_tag.get('commit', '')}")
                lines.append(f"Receipt ID: {execution_tag.get('receipt_id', '')}")

            git_commit = report.get("git_commit", {})

            if git_commit:
                lines.append("\nGit Commit Engine:")
                lines.append("-" * 40)
                lines.append(f"Status: {git_commit.get('status')}")
                lines.append(f"OK: {git_commit.get('ok')}")
                lines.append(f"Reason: {git_commit.get('reason', '')}")
                lines.append(f"Commit Hash: {git_commit.get('commit_hash', '')}")

                files = git_commit.get("files", [])
                lines.append(f"Files: {len(files)}")

                for item in files:
                    lines.append(f"- {item}")

            skipped_targets = apply_session.get("skipped_targets", [])

            if skipped_targets:
                lines.append("\nSkipped Targets:")

                for item in skipped_targets:
                    lines.append(
                        f"- {item.get('source')} | "
                        f"{item.get('status')}"
                    )

            backups = apply_session.get("backups", [])

            if backups:
                lines.append("\nBackups:")

                for item in backups:
                    lines.append(
                        f"- {item.get('source')} "
                        f"-> {item.get('backup')}"
                    )

    def _contract(self, lines, report):
        contract = report.get("apply_contract", {})

        lines.append("\nControlled Apply Contract:")
        lines.append("-" * 40)
        lines.append(contract.get("status", "unknown"))
        lines.append(contract.get("message", ""))

        violations = contract.get("violations", [])

        if violations:
            lines.append("Violations:")

            for item in violations:
                lines.append(f"- {item}")

    def _state(self, lines, report):
        state = report.get("execution_state", {})

        lines.append("\nExecution State:")
        lines.append("-" * 40)

        lines.append(
            state.get("current_state", "unknown")
        )

        lines.append(
            f"Transitions: {state.get('transition_count', 0)}"
        )

        for item in state.get("transitions", []):
            lines.append(
                f"- {item['from_state']} -> "
                f"{item['to_state']} | "
                f"{item['reason']}"
            )
