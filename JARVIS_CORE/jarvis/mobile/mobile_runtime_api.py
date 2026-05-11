from jarvis.config import RuntimeConfigManager
from jarvis.logging import RuntimeLogger
from jarvis.security import RuntimePermissionManager
from jarvis.learning import AgentLearningMemory


class JarvisMobileRuntimeAPI:
    def __init__(self):
        self.config_manager = RuntimeConfigManager()
        self.logger = RuntimeLogger()
        self.permission_manager = RuntimePermissionManager()
        self.learning_memory = AgentLearningMemory()

    def get_status(self):
        config = self.config_manager.load()
        permission = self.permission_manager.get_profile(config.permission_level)
        recent_events = self.logger.read_recent(limit=10)

        return {
            "runtime": {
                "mode": config.runtime_mode,
                "permission_level": config.permission_level,
                "voice_enabled": config.voice_enabled,
                "git_tags_enabled": config.git_tags_enabled,
                "isolated_branches_enabled": config.isolated_branches_enabled,
                "real_apply_requires_approval": config.real_apply_requires_approval,
            },
            "permissions": {
                "profile": permission.name,
                "allow_real_apply": permission.allow_real_apply,
                "allow_git_write": permission.allow_git_write,
                "allow_branching": permission.allow_branching,
                "allow_shell_execution": permission.allow_shell_execution,
            },
            "events": recent_events,
            "learning": {
                "best_agent_python": self.learning_memory.best_agent("python"),
                "ranked_agents_python": self.learning_memory.rank_agents("python"),
            },
            "health": {
                "status": "online",
                "source": "jarvis_mobile_runtime_api",
            },
        }
