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
            }

        result = {
            "timestamp": self._now(),
            "runtime": "recovery_recommendation_engine",
            "phase": "Autonomous Recovery Recommendation Engine",
            "layer": "1/5",
            "bounded": True,
            "rollback_safe": True,
            "governed": True,
            "dry_run": dry_run,
            "dangerous_autonomous_apply": False,
            "recommendation_state": "generated",
            "recommendations": recommendations,
        }

        out = self.runtime_logs / "recovery_recommendations.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        return result


if __name__ == "__main__":
    result = RecoveryRecommendationEngine().execute(dry_run=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))
