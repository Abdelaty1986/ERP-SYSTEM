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
