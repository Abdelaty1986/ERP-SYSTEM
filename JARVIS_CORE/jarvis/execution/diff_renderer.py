class DiffRenderer:
    def render_patch_report(self, patch_plan: dict) -> str:
        lines = []
        lines.append("Safe Patch Proposal")
        lines.append("=" * 40)
        lines.append(f"Task: {patch_plan.get('task')}")
        lines.append(f"Status: {patch_plan.get('status')}")
        lines.append(f"Change Type: {patch_plan.get('change_type')}")
        lines.append(f"Risk Level: {patch_plan.get('risk_level')}")
        lines.append(f"Requires Approval: {patch_plan.get('requires_approval')}")
        lines.append("")

        for index, patch in enumerate(patch_plan.get("patches", []), start=1):
            lines.append(f"Patch #{index}")
            lines.append("-" * 40)
            lines.append(f"File: {patch.get('file_path')}")
            lines.append(f"Type: {patch.get('change_type')}")
            lines.append(f"Risk: {patch.get('risk_level')}")
            lines.append(f"Reason: {patch.get('reason')}")
            lines.append("")
            lines.append("Diff Preview:")
            lines.append(patch.get("diff_preview") or "No diff preview.")
            lines.append("")

        lines.append("Notes:")
        for note in patch_plan.get("notes", []):
            lines.append(f"- {note}")

        return "\n".join(lines)
