import json
from pathlib import Path
from datetime import datetime, timezone


class RecoveryRecommendationEngine:
    def __init__(self):
        self.root = Path("JARVIS_CORE")
        self.runtime_logs = self.root / "runtime_logs"
        self.runtime_logs.mkdir(parents=True, exist_ok=True)

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def _read_json(self, path):
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return {}

    def _collect_runtime_sources(self):
        files = {
            "provider_health": self.runtime_logs / "llm_provider_health.json",
            "provider_recovery": self.runtime_logs / "provider_recovery_executor.json",
            "provider_ranking": self.runtime_logs / "provider_ranking_runtime.json",
            "confidence_decay": self.runtime_logs / "confidence_decay_runtime.json",
        }
        return {name: self._read_json(path) for name, path in files.items()}

    def _provider_names(self, sources):
        names = set()
        for data in sources.values():
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, dict):
                        names.add(key)
                for section in ("providers", "actions", "rankings", "decay"):
                    block = data.get(section)
                    if isinstance(block, dict):
                        names.update(block.keys())
        return sorted(names)

    def _score_provider(self, provider, sources):
        score = 50
        reasons = []

        text_blob = json.dumps(sources, ensure_ascii=False).lower()

        if provider.lower() in text_blob:
            score += 10
            reasons.append("provider observed in runtime sources")

        negative_terms = ["429", "rate limit", "timeout", "error", "failed", "stale", "cooldown"]
        for term in negative_terms:
            if term in text_blob:
                score -= 5

        positive_terms = ["online", "healthy", "passed", "stable", "available"]
        for term in positive_terms:
            if term in text_blob:
                score += 3

        score = max(0, min(100, score))
        return score, reasons

    def _recommend_action(self, score):
        if score >= 75:
            return "keep_active"
        if score >= 55:
            return "retry_with_monitoring"
        if score >= 35:
            return "cooldown_then_probe"
        return "rehabilitation_required"

    def _rehabilitation_plan(self, provider, score, action):
        if action == "keep_active":
            steps = ["continue normal routing", "keep passive monitoring enabled"]
            priority = "low"
        elif action == "retry_with_monitoring":
            steps = ["allow bounded retry", "monitor next provider response", "avoid priority boost until stable"]
            priority = "medium"
        elif action == "cooldown_then_probe":
            steps = ["apply cooldown recommendation", "run targeted health probe", "restore only after successful probe"]
            priority = "high"
        else:
            steps = ["remove from preferred routing", "require manual or scheduled probe", "do not restore without stable signal"]
            priority = "critical"

        return {
            "provider": provider,
            "rehabilitation_priority": priority,
            "rehabilitation_steps": steps,
            "restoration_allowed": action in ("keep_active", "retry_with_monitoring"),
            "requires_probe_before_restore": action in ("cooldown_then_probe", "rehabilitation_required"),
            "bounded": True,
            "direct_apply_allowed": False,
        }


    def _retry_cooldown_policy(self, score, action):
        policies = {
            "keep_active": (True, 1, 0, False, 0),
            "retry_with_monitoring": (True, 1, 60, False, 5),
            "cooldown_then_probe": (False, 0, 300, True, 15),
            "rehabilitation_required": (False, 0, 900, True, 30),
        }
        retry_allowed, max_retry_attempts, cooldown_seconds, probe_required, routing_penalty = policies.get(
            action,
            policies["rehabilitation_required"],
        )

        return {
            "retry_allowed": retry_allowed,
            "max_retry_attempts": max_retry_attempts,
            "cooldown_seconds": cooldown_seconds,
            "probe_required": probe_required,
            "routing_penalty": routing_penalty,
            "bounded": True,
            "direct_apply_allowed": False,
        }


    def _recovery_scoring_runtime(self, score, action):
        recovery_confidence = min(100, score + 10)

        if action == "keep_active":
            routing_stability = 95
            rehabilitation_urgency = "low"
            operational_state = "stable"

        elif action == "retry_with_monitoring":
            routing_stability = 70
            rehabilitation_urgency = "moderate"
            operational_state = "recovering"

        elif action == "cooldown_then_probe":
            routing_stability = 40
            rehabilitation_urgency = "high"
            operational_state = "degraded"

        else:
            routing_stability = 15
            rehabilitation_urgency = "critical"
            operational_state = "unstable"

        return {
            "recovery_confidence": recovery_confidence,
            "routing_stability": routing_stability,
            "rehabilitation_urgency": rehabilitation_urgency,
            "operational_state": operational_state,
            "bounded": True,
            "direct_apply_allowed": False,
        }


    def _hud_summary(self, recommendations):
        states = {}
        for provider, data in recommendations.items():
            scoring = data.get("recovery_scoring_runtime", {})
            policy = data.get("retry_cooldown_policy", {})
            states[provider] = {
                "provider": provider,
                "recommended_action": data.get("recommended_action"),
                "recovery_score": data.get("recovery_score"),
                "operational_state": scoring.get("operational_state", "unknown"),
                "routing_stability": scoring.get("routing_stability", 0),
                "rehabilitation_urgency": scoring.get("rehabilitation_urgency", "unknown"),
                "retry_allowed": policy.get("retry_allowed", False),
                "cooldown_seconds": policy.get("cooldown_seconds", 0),
            }

        return {
            "hud_state": "ready",
            "title": "Autonomous Recovery Recommendations",
            "provider_count": len(states),
            "providers": states,
            "bounded": True,
            "direct_apply_allowed": False,
        }

    def execute(self, dry_run=True):
        sources = self._collect_runtime_sources()
        providers = self._provider_names(sources)

        if not providers:
            providers = ["gemini", "groq", "openrouter"]

        recommendations = {}

        for provider in providers:
            score, reasons = self._score_provider(provider, sources)
            action = self._recommend_action(score)

            recommendations[provider] = {
                "provider": provider,
                "recovery_score": score,
                "recommended_action": action,
                "bounded": True,
                "dry_run": dry_run,
                "direct_apply_allowed": False,
                "reasons": reasons or ["baseline bounded recovery evaluation"],
                "rehabilitation": self._rehabilitation_plan(provider, score, action),
                "retry_cooldown_policy": self._retry_cooldown_policy(score, action),
                "recovery_scoring_runtime": self._recovery_scoring_runtime(score, action),
            }

        result = {
            "timestamp": self._now(),
            "runtime": "recovery_recommendation_engine",
            "phase": "Autonomous Recovery Recommendation Engine",
            "layer": "5/5",
            "bounded": True,
            "rollback_safe": True,
            "governed": True,
            "dry_run": dry_run,
            "dangerous_autonomous_apply": False,
            "recommendation_state": "generated",
            "hud": self._hud_summary(recommendations),
            "recommendations": recommendations,
        }

        out = self.runtime_logs / "recovery_recommendations.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        return result


if __name__ == "__main__":
    result = RecoveryRecommendationEngine().execute(dry_run=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))
