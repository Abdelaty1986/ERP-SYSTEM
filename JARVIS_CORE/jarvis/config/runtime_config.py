from dataclasses import dataclass, asdict
from pathlib import Path
import json


@dataclass
class RuntimeConfig:
    runtime_mode: str = "controlled_real_execution"
    permission_level: str = "gated_apply"
    voice_enabled: bool = True
    git_tags_enabled: bool = True
    isolated_branches_enabled: bool = True
    real_apply_requires_approval: bool = True

    def to_dict(self):
        return asdict(self)


class RuntimeConfigManager:
    def __init__(self, config_path=None):
        self.config_path = Path(config_path or "JARVIS_CORE/runtime_config.json")

    def default_config(self):
        return RuntimeConfig()

    def load(self):
        # Always read authoritative mode from execution_mode_manager
        try:
            from jarvis.runtime.execution_mode_manager import read_mode
            mode_data = read_mode()
            actual_mode = mode_data.get("mode", "controlled_real_execution")
        except Exception:
            actual_mode = "controlled_real_execution"

        # Map mode to permission level
        mode_to_permission = {
            "simulation_only": "sandbox_only",
            "controlled_real_execution": "gated_apply",
            "supervised_real_execution": "supervised",
        }
        permission = mode_to_permission.get(actual_mode, "gated_apply")

        return RuntimeConfig(
            runtime_mode=actual_mode,
            permission_level=permission,
        )

    def save(self, config: RuntimeConfig):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(config.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return self.config_path

    def ensure_exists(self):
        if not self.config_path.exists():
            return self.save(self.default_config())
        return self.config_path
