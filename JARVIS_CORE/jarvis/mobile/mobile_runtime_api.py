from jarvis.config import RuntimeConfigManager
from jarvis.logging import RuntimeLogger
from jarvis.security import RuntimePermissionManager
from jarvis.learning import AgentLearningMemory
from jarvis.consensus import MultiAgentConsensusEngine, AgentOpinion
from jarvis.repair import AutonomousRepairLoop
from jarvis.health import RuntimeHealthMonitor
from jarvis.commands import RuntimeCommandAPI
from jarvis.execution.runtime_worker_state import RuntimeWorkerState


class JarvisMobileRuntimeAPI:
    def __init__(self):
        self.config_manager = RuntimeConfigManager()
        self.logger = RuntimeLogger()
        self.permission_manager = RuntimePermissionManager()
        self.learning_memory = AgentLearningMemory()
        self.consensus_engine = MultiAgentConsensusEngine()
        self.repair_loop = AutonomousRepairLoop()
        self.health_monitor = RuntimeHealthMonitor('.')
        self.command_api = RuntimeCommandAPI(logger=self.logger)

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
            "consensus": self.consensus_engine.evaluate([
                AgentOpinion("gemini_free", "approve", 0.88, "low", "Runtime status safe"),
                AgentOpinion("groq_free", "approve", 0.80, "low", "No unsafe action requested"),
                AgentOpinion("local_reviewer", "approve", 0.92, "low", "Safety gates active"),
            ]),
            "repair": self.repair_loop.propose_repair_plan(
                task="runtime health monitoring",
                failure_output="ModuleNotFoundError: simulated runtime diagnostic"
            ),
            "runtime_health": self.health_monitor.overall_health(),
            "commands": {
                "allowed": sorted(list(RuntimeCommandAPI.ALLOWED_COMMANDS)),
            },
            "command_queue": self.command_api.read_queue(limit=10),
            "worker_state": RuntimeWorkerState.read(),
            "health": {
                "status": "online",
                "source": "jarvis_mobile_runtime_api",
            },
        }


# Runtime Correlation HUD Snapshot
def load_runtime_correlation_snapshot():
    import json
    from pathlib import Path

    path = Path("JARVIS_CORE/runtime_logs/runtime_correlation_analysis.json")

    default = {
        "available": False,
        "correlation_strength": "unknown",
        "forecast_state": "unknown",
        "escalation_risk": "unknown",
        "wake_cycle_count": 0,
        "silence_detection_count": 0,
        "cognition_persistence": 0,
        "correlation_insights": [],
        "safe_mode": True,
        "bounded": True,
    }

    if not path.exists():
        return default

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        default.update(data)
        default["available"] = True
        return default
    except Exception as exc:
        default["error"] = str(exc)
        return default

