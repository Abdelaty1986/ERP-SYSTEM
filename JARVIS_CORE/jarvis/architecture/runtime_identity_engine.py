class RuntimeIdentityEngine:
    def build_identity(self, goal_data, deliberation_data, arbitration_data, reflection_data):
        goal_summary = goal_data.get("summary", {}) if isinstance(goal_data, dict) else {}
        goal = goal_data.get("goal", {}) if isinstance(goal_data, dict) else {}

        deliberation_summary = deliberation_data.get("summary", {}) if isinstance(deliberation_data, dict) else {}
        arbitration_summary = arbitration_data.get("summary", {}) if isinstance(arbitration_data, dict) else {}
        reflection_summary = reflection_data.get("summary", {}) if isinstance(reflection_data, dict) else {}

        identity = {
            "name": "JARVIS CORE",
            "runtime_type": "bounded_ai_engineering_runtime",
            "specialization": "safe architecture cognition and engineering planning",
            "operational_mode": "cognitive_planning_only",
            "safety_posture": "human_review_required",
            "autonomous_apply": False,
            "bounded": True,
        }

        current_state = {
            "active_goal": goal.get("goal_id"),
            "goal_status": goal_summary.get("status"),
            "goal_alignment": goal_summary.get("alignment_state"),
            "consensus_state": deliberation_summary.get("consensus_state"),
            "best_strategy": arbitration_summary.get("best_strategy"),
            "reflection_score": reflection_summary.get("reflection_score"),
            "forecast_state": reflection_summary.get("forecast_state"),
        }

        continuity = self._continuity_state(goal_summary, deliberation_summary, reflection_summary)

        return {
            "bounded": True,
            "mode": "runtime_identity_only",
            "autonomous_apply": False,
            "identity": identity,
            "current_state": current_state,
            "continuity": continuity,
            "self_description": self._self_description(identity, current_state, continuity),
            "notes": [
                "Runtime identity summarizes the current cognitive operating state.",
                "This layer does not execute actions.",
                "All engineering actions remain human-governed."
            ],
        }

    def _continuity_state(self, goal_summary, deliberation_summary, reflection_summary):
        score = 0

        if goal_summary.get("alignment_state") == "strong_alignment":
            score += 35

        if deliberation_summary.get("consensus_state") == "strong_consensus":
            score += 30

        if int(reflection_summary.get("reflection_score", 0) or 0) >= 90:
            score += 35

        if score >= 90:
            state = "strong_runtime_continuity"
        elif score >= 60:
            state = "moderate_runtime_continuity"
        else:
            state = "weak_runtime_continuity"

        return {
            "score": score,
            "state": state,
            "reason": "Continuity is derived from goal alignment, consensus, and reflection coherence."
        }

    def _self_description(self, identity, state, continuity):
        return (
            f"{identity['name']} is operating as a {identity['runtime_type']} "
            f"in {identity['operational_mode']} mode. "
            f"Current goal is {state.get('active_goal')} with {state.get('goal_alignment')} alignment. "
            f"Best strategy is {state.get('best_strategy')} and continuity is {continuity.get('state')}."
        )
