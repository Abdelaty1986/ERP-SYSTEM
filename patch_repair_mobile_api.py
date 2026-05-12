from pathlib import Path

path = Path("JARVIS_CORE/jarvis/mobile/mobile_runtime_api.py")
text = path.read_text(encoding="utf-8")

if "from jarvis.repair import AutonomousRepairLoop" not in text:
    text = text.replace(
        "from jarvis.consensus import MultiAgentConsensusEngine, AgentOpinion",
        "from jarvis.consensus import MultiAgentConsensusEngine, AgentOpinion\nfrom jarvis.repair import AutonomousRepairLoop"
    )

if "self.repair_loop" not in text:
    text = text.replace(
        "self.consensus_engine = MultiAgentConsensusEngine()",
        "self.consensus_engine = MultiAgentConsensusEngine()\n        self.repair_loop = AutonomousRepairLoop()"
    )

if '"repair"' not in text:
    text = text.replace(
        '''            "consensus": self.consensus_engine.evaluate([
                AgentOpinion("gemini_free", "approve", 0.88, "low", "Runtime status safe"),
                AgentOpinion("groq_free", "approve", 0.80, "low", "No unsafe action requested"),
                AgentOpinion("local_reviewer", "approve", 0.92, "low", "Safety gates active"),
            ]),
            "health": {''',
        '''            "consensus": self.consensus_engine.evaluate([
                AgentOpinion("gemini_free", "approve", 0.88, "low", "Runtime status safe"),
                AgentOpinion("groq_free", "approve", 0.80, "low", "No unsafe action requested"),
                AgentOpinion("local_reviewer", "approve", 0.92, "low", "Safety gates active"),
            ]),
            "repair": self.repair_loop.propose_repair_plan(
                task="runtime health monitoring",
                failure_output="ModuleNotFoundError: simulated runtime diagnostic"
            ),
            "health": {'''
    )

path.write_text(text, encoding="utf-8")
print("Repair loop added to mobile API")
