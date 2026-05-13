from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone


class RuntimeAudit:
    def __init__(self, root: str = "JARVIS_CORE"):
        self.root = Path(root)
        self.memory_dir = self.root / "runtime_memory"
        self.logs_dir = self.root / "runtime_logs"
        self.jarvis_dir = self.root / "jarvis"

        self.required_memory = {
            "approval_gateway": self.memory_dir / "approval_gateway.json",
            "approval_lineage": self.memory_dir / "approval_lineage.json",
            "approval_transitions": self.memory_dir / "approval_transitions.json",
            "execution_journal": self.memory_dir / "execution_journal.json",
            "safe_execution_queue": self.memory_dir / "safe_execution_queue.json",
            "agent_skill_memory": self.memory_dir / "agent_skill_memory.json",
            "agent_routing_memory": self.memory_dir / "agent_routing_memory.json",
            "task_chain_memory": self.memory_dir / "task_chain_memory.json",
            "task_execution_simulation": self.memory_dir / "task_execution_simulation.json",
            "rollback_checkpoint_memory": self.memory_dir / "rollback_checkpoint_memory.json",
            "controlled_apply_decision": self.memory_dir / "controlled_apply_decision.json",
            "human_approved_apply": self.memory_dir / "human_approved_apply.json",
            "learning_summary": self.memory_dir / "learning_summary.json",
            "failure_summary": self.memory_dir / "failure_summary.json",
        }

        self.required_modules = {
            "runtime_aggregator": self.jarvis_dir / "runtime" / "runtime_aggregator.py",
            "runtime_visibility": self.jarvis_dir / "runtime" / "runtime_visibility.py",
            "agent_skill_memory": self.jarvis_dir / "runtime" / "agent_skill_memory.py",
            "dynamic_agent_routing_engine": self.jarvis_dir / "architecture" / "dynamic_agent_routing_engine.py",
            "sandbox_manager": self.jarvis_dir / "execution" / "sandbox_manager.py",
            "sandbox_apply_simulator": self.jarvis_dir / "execution" / "sandbox_apply_simulator.py",
            "approval_manager": self.jarvis_dir / "execution" / "approval_manager.py",
            "real_apply_switch": self.jarvis_dir / "execution" / "real_apply_switch.py",
        }

    def _load_json(self, path: Path):
        if not path.exists():
            return None, "missing"

        try:
            return json.loads(path.read_text(encoding="utf-8")), "ok"
        except Exception:
            return None, "corrupted"

    def _bool_guard(self, data, key, expected=False):
        if not isinstance(data, dict):
            return "unknown"

        value = data.get(key)

        if value is expected:
            return "safe"

        if value is None:
            return "not_declared"

        return "unsafe_or_unexpected"

    def audit_memory(self):
        results = {}

        for name, path in self.required_memory.items():
            data, state = self._load_json(path)
            results[name] = {
                "exists": path.exists(),
                "state": state,
                "path": str(path),
            }

            if isinstance(data, dict):
                results[name]["bounded"] = data.get("bounded")
                results[name]["autonomous_apply"] = data.get("autonomous_apply")
                results[name]["real_apply_enabled"] = data.get("real_apply_enabled")

        return results

    def audit_modules(self):
        return {
            name: {
                "exists": path.exists(),
                "path": str(path),
            }
            for name, path in self.required_modules.items()
        }

    def detect_duplicates(self):
        return {
            "agent_skill_layers": [
                str(self.jarvis_dir / "architecture" / "agent_skill_scoring_engine.py"),
                str(self.jarvis_dir / "runtime" / "agent_skill_memory.py"),
            ],
            "routing_layers": [
                str(self.jarvis_dir / "architecture" / "dynamic_agent_routing_engine.py"),
                str(self.memory_dir / "agent_routing_memory.json"),
            ],
            "note": (
                "Duplicates here are architectural overlaps, not errors. "
                "Prefer runtime modules as unified read interfaces and architecture modules as engines."
            ),
        }

    def security_summary(self, memory_results):
        unsafe = []
        missing_flags = []

        for name, item in memory_results.items():
            if item.get("autonomous_apply") is True:
                unsafe.append(f"{name}: autonomous_apply=true")

            if item.get("real_apply_enabled") is True:
                unsafe.append(f"{name}: real_apply_enabled=true")

            if "autonomous_apply" not in item:
                missing_flags.append(f"{name}: autonomous_apply not declared")

        return {
            "execution_unlock_allowed": False,
            "autonomous_apply_expected": False,
            "real_apply_expected": False,
            "unsafe_findings": unsafe,
            "missing_flag_notes": missing_flags[:10],
            "security_state": "safe_locked" if not unsafe else "review_required",
        }

    def run(self):
        memory = self.audit_memory()
        modules = self.audit_modules()
        security = self.security_summary(memory)

        missing_memory = [
            name for name, item in memory.items()
            if not item.get("exists")
        ]

        missing_modules = [
            name for name, item in modules.items()
            if not item.get("exists")
        ]

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "audit": "runtime_audit",
            "bounded": True,
            "real_apply_enabled": False,
            "autonomous_apply": False,
            "memory_count": len(memory),
            "module_count": len(modules),
            "missing_memory": missing_memory,
            "missing_modules": missing_modules,
            "security": security,
            "duplicates": self.detect_duplicates(),
            "memory": memory,
            "modules": modules,
            "final_state": (
                "stable"
                if not missing_memory and not missing_modules
                and security["security_state"] == "safe_locked"
                else "review_required"
            ),
        }

        return report


if __name__ == "__main__":
    report = RuntimeAudit().run()
    print(json.dumps(report, ensure_ascii=False, indent=2))
