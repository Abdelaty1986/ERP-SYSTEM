import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"

INPUTS = {
    "health": MEMORY_DIR / "cognition_health_report.json",
    "silence": MEMORY_DIR / "runtime_silence_detection.json",
    "stability": MEMORY_DIR / "cognitive_stability_analysis.json",
    "long_running_loop": MEMORY_DIR / "long_running_runtime_loop.json",
    "reflection": MEMORY_DIR / "cognitive_reflection_runtime.json",
}

HUD_REPORT = MEMORY_DIR / "runtime_self_monitoring_hud.json"


class RuntimeSelfMonitoringHUD:
    def _read_json(self, path):
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def build(self):
        data = {name: self._read_json(path) for name, path in INPUTS.items()}

        hud = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "runtime_self_monitoring_hud",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "hud_state": "online",
            "cognitive_supervision": {
                "health_state": (data["health"] or {}).get("health_state", "unknown"),
                "health_score": (data["health"] or {}).get("health_score", 0),
                "silence_state": (data["silence"] or {}).get("silence_state", "unknown"),
                "silence_risk": (data["silence"] or {}).get("silence_risk", "unknown"),
                "stability_state": (data["stability"] or {}).get("stability_state", "unknown"),
                "stability_score": (data["stability"] or {}).get("stability_score", 0),
                "loop_state": (data["long_running_loop"] or {}).get("loop_state", "unknown"),
                "reflection_state": (data["reflection"] or {}).get("reflection_state", "unknown"),
                "next_runtime_allowed": (data["reflection"] or {}).get("next_runtime_allowed", False),
            },
            "safety": {
                "human_approval_required": True,
                "autonomous_unlock_allowed": False,
                "hud_is_monitoring_only": True,
            },
            "status_text": self._status_text(data),
        }

        HUD_REPORT.write_text(
            json.dumps(hud, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return hud

    def _status_text(self, data):
        reflection = data.get("reflection") or {}
        stability = data.get("stability") or {}

        if reflection.get("reflection_state") == "clear" and stability.get("stability_state") == "stable":
            return "Persistent Cognitive Runtime is stable, active, and visible in HUD."

        return "Persistent Cognitive Runtime requires attention before higher runtime expansion."


def build_hud():
    return RuntimeSelfMonitoringHUD().build()


if __name__ == "__main__":
    print(json.dumps(build_hud(), ensure_ascii=False, indent=2))
