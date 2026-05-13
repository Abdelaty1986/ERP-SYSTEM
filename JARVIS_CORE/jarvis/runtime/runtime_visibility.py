from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class RuntimeVisibility:
    def __init__(self, root: str = "JARVIS_CORE"):
        self.root = Path(root)

        self.snapshot_file = (
            self.root / "runtime_logs" / "runtime_aggregation_snapshot.json"
        )

        self.output_file = (
            self.root / "runtime_logs" / "runtime_visibility_summary.json"
        )

    def _load_snapshot(self):
        if not self.snapshot_file.exists():
            return {}

        try:
            return json.loads(
                self.snapshot_file.read_text(encoding="utf-8")
            )
        except Exception:
            return {}

    def build_visibility_summary(self):
        snapshot = self._load_snapshot()

        runtimes = snapshot.get("aggregated_runtimes", {})

        visible = []
        hidden = []

        for name, payload in runtimes.items():
            if payload.get("exists"):
                visible.append(name)
            else:
                hidden.append(name)

        audit_data = (
            runtimes.get("runtime_audit", {})
            .get("data", {})
        )

        audit_security = audit_data.get("security", {})

        audit_summary = {
            "audit_final_state": audit_data.get("final_state", "unknown"),
            "security_state": audit_security.get("security_state", "unknown"),
            "missing_memory_count": len(audit_data.get("missing_memory", [])),
            "missing_modules_count": len(audit_data.get("missing_modules", [])),
            "duplicate_layer_notes": (
                audit_data.get("duplicates", {})
                .get("note", "")
            ),
        }

        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "visibility_runtime": "runtime_visibility_layer",
            "bounded": True,
            "autonomous_apply": False,
            "real_apply_enabled": False,
            "execution_unlock_allowed": False,
            "aggregation_state": snapshot.get("aggregation_state", "unknown"),
            "visible_runtime_count": len(visible),
            "hidden_runtime_count": len(hidden),
            "visible_runtimes": visible,
            "hidden_runtimes": hidden,
            "audit_summary": audit_summary,
            "global_runtime_state": (
                "stable"
                if snapshot.get("aggregation_state") == "stable"
                else "review_required"
            ),
            "governance": {
                "approval_required": True,
                "execution_locked": True,
                "rollback_awareness": True,
                "lineage_visibility": True,
                "bounded_execution": True,
            }
        }

        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        self.output_file.write_text(
            json.dumps(summary, indent=2),
            encoding="utf-8"
        )

        return summary


if __name__ == "__main__":
    print(json.dumps(
        RuntimeVisibility().build_visibility_summary(),
        indent=2
    ))
