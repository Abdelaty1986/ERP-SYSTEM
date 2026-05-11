from dataclasses import dataclass, asdict
from pathlib import Path
import json


@dataclass
class RuntimeConfig:
    runtime_mode: str = "simulation_only"
    permission_level: str = "sandbox_only"
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
        if not self.config_path.exists():
            return self.default_config()

        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        return RuntimeConfig(**data)

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
