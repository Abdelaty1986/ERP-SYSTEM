from pathlib import Path

path = Path("app.py")
text = path.read_text(encoding="utf-8")

route = r'''

@app.route("/jarvis/mobile/api/architecture/arbitration")
def jarvis_mobile_strategy_arbitration():
    try:
        from JARVIS_CORE.jarvis.architecture.architecture_memory import ArchitectureMemory
        from JARVIS_CORE.jarvis.architecture.runtime_forecast_engine import RuntimeForecastEngine
        from JARVIS_CORE.jarvis.architecture.recommendation_evolution_engine import RecommendationEvolutionEngine
        from JARVIS_CORE.jarvis.architecture.strategy_simulation_engine import StrategySimulationEngine
        from JARVIS_CORE.jarvis.architecture.safe_execution_strategy_planner import SafeExecutionStrategyPlanner
        from JARVIS_CORE.jarvis.architecture.runtime_reflection_engine import RuntimeReflectionEngine
        from JARVIS_CORE.jarvis.architecture.cognitive_decision_engine import CognitiveDecisionEngine
        from JARVIS_CORE.jarvis.architecture.strategy_arbitration_engine import StrategyArbitrationEngine

        memory = ArchitectureMemory(".").build_evolution_report()
        forecast = RuntimeForecastEngine().analyze(memory)
        evolution = RecommendationEvolutionEngine().analyze(memory)
        strategy = StrategySimulationEngine().simulate(evolution)
        plan = SafeExecutionStrategyPlanner().build_plan(strategy)
        reflection = RuntimeReflectionEngine().reflect(forecast, evolution, strategy, plan)
        decision = CognitiveDecisionEngine().decide(reflection, strategy, plan)

        data = StrategyArbitrationEngine().arbitrate(decision)
        return jsonify(data)

    except Exception as exc:
        return jsonify({
            "bounded": True,
            "mode": "executive_arbitration_only",
            "autonomous_apply": False,
            "error": str(exc)
        }), 500
'''

if "/jarvis/mobile/api/architecture/arbitration" in text:
    print("strategy arbitration endpoint already exists")
else:
    marker = 'if __name__ == "__main__":'
    if marker not in text:
        raise SystemExit("main block not found")
    text = text.replace(marker, route + "\n\n" + marker, 1)
    path.write_text(text, encoding="utf-8")
    print("strategy arbitration endpoint added")
