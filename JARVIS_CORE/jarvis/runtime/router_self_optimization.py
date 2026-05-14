import json
from pathlib import Path
from datetime import datetime, timezone


ROOT = Path("JARVIS_CORE")
MEMORY_DIR = ROOT / "runtime_memory"
MEMORY_FILE = MEMORY_DIR / "router_optimization_memory.json"


class RouterSelfOptimization:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def _default_memory(self):
        return {
            "runtime": "router_self_optimization",
            "bounded": True,
            "dangerous_autonomous_apply": False,
            "last_updated": self._now(),
            "routing_weights": {
                "gemini": {
                    "trust": 0.70,
                    "latency": 0.50,
                    "availability": 0.70,
                    "recovery": 0.60,
                    "final_weight": 0.625
                },
                "groq": {
                    "trust": 0.65,
                    "latency": 0.75,
                    "availability": 0.65,
                    "recovery": 0.55,
                    "final_weight": 0.650
                },
                "openrouter": {
                    "trust": 0.55,
                    "latency": 0.45,
                    "availability": 0.50,
                    "recovery": 0.65,
                    "final_weight": 0.537
                }
            },
            "optimization_state": "initialized",
            "notes": [
                "Layer 1 initialized dynamic routing weights",
                "No autonomous apply enabled",
                "Weights are advisory only"
            ]
        }

    def load_memory(self):
        if not MEMORY_FILE.exists():
            return self._default_memory()

        try:
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return self._default_memory()

    def calculate_weight(self, data):
        trust = float(data.get("trust", 0))
        latency = float(data.get("latency", 0))
        availability = float(data.get("availability", 0))
        recovery = float(data.get("recovery", 0))

        weight = (
            trust * 0.35 +
            latency * 0.20 +
            availability * 0.30 +
            recovery * 0.15
        )
        return round(weight, 3)

    def balance_provider(self, provider, data):
        final_weight = float(data.get("final_weight", 0))
        availability = float(data.get("availability", 0))
        latency = float(data.get("latency", 0))
        recovery = float(data.get("recovery", 0))

        if availability < 0.45:
            state = "deprioritized"
            reason = "low_availability"
            adjustment = -0.10
        elif latency < 0.45:
            state = "latency_limited"
            reason = "latency_pressure"
            adjustment = -0.05
        elif recovery >= 0.65 and final_weight >= 0.50:
            state = "rehabilitation_candidate"
            reason = "recovery_strength_detected"
            adjustment = 0.04
        else:
            state = "balanced"
            reason = "within_safe_operating_range"
            adjustment = 0.00

        balanced_weight = max(0, min(1, round(final_weight + adjustment, 3)))

        return {
            "provider": provider,
            "state": state,
            "reason": reason,
            "base_weight": final_weight,
            "adjustment": adjustment,
            "balanced_weight": balanced_weight,
            "bounded": True
        }

    def build_balancing_plan(self, memory):
        plan = []
        for provider, data in memory.get("routing_weights", {}).items():
            plan.append(self.balance_provider(provider, data))

        return sorted(
            plan,
            key=lambda item: item["balanced_weight"],
            reverse=True
        )

    def build_adaptive_decision(self, balancing_plan):
        if not balancing_plan:
            return {
                "decision_state": "no_candidates",
                "bounded": True
            }

        primary = balancing_plan[0]
        fallback = balancing_plan[1] if len(balancing_plan) > 1 else primary

        confidence = "low"

        if primary["balanced_weight"] >= 0.75:
            confidence = "high"
        elif primary["balanced_weight"] >= 0.60:
            confidence = "moderate"

        decision = {
            "decision_state": "adaptive_routing_ready",
            "preferred_provider": primary["provider"],
            "preferred_weight": primary["balanced_weight"],
            "preferred_state": primary["state"],
            "fallback_provider": fallback["provider"],
            "fallback_weight": fallback["balanced_weight"],
            "routing_confidence": confidence,
            "bounded": True,
            "autonomous_apply": False,
            "notes": [
                "Adaptive routing remains advisory",
                "No autonomous execution enabled"
            ]
        }

        return decision


    def build_routing_history_entry(self, adaptive_decision):
        return {
            "timestamp": self._now(),
            "preferred_provider": adaptive_decision.get(
                "preferred_provider"
            ),
            "fallback_provider": adaptive_decision.get(
                "fallback_provider"
            ),
            "routing_confidence": adaptive_decision.get(
                "routing_confidence"
            ),
            "decision_state": adaptive_decision.get(
                "decision_state"
            ),
            "bounded": True
        }


    def execute(self):
        memory = self.load_memory()

        for provider, data in memory.get("routing_weights", {}).items():
            data["final_weight"] = self.calculate_weight(data)

        balancing_plan = self.build_balancing_plan(memory)

        memory["ranking"] = [
            {
                "provider": item["provider"],
                "final_weight": item["base_weight"],
                "balanced_weight": item["balanced_weight"],
                "state": item["state"]
            }
            for item in balancing_plan
        ]

        adaptive_decision = self.build_adaptive_decision(
            balancing_plan
        )

        history_entry = self.build_routing_history_entry(
            adaptive_decision
        )

        history = memory.get("routing_history", [])
        history.append(history_entry)

        memory["routing_history"] = history[-15:]
        memory["adaptive_decision"] = adaptive_decision
        memory["balancing_plan"] = balancing_plan
        memory["last_updated"] = self._now()
        memory["optimization_state"] = "provider_balancing_ready"
        memory["bounded"] = True
        memory["dangerous_autonomous_apply"] = False

        if "Layer 2 added provider balancing engine" not in memory.get("notes", []):
            memory.setdefault("notes", []).append(
                "Layer 2 added provider balancing engine"
            )

        MEMORY_FILE.write_text(
            json.dumps(memory, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return memory


if __name__ == "__main__":
    result = RouterSelfOptimization().execute()
    print(json.dumps(result, ensure_ascii=False, indent=2))
