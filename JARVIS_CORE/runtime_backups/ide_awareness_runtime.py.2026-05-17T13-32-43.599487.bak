import json
import os
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ROOT.parent
MEMORY_DIR = ROOT / "runtime_memory"
LOGS_DIR = ROOT / "runtime_logs"
OUTPUT_PATH = MEMORY_DIR / "ide_awareness_runtime.json"
LOG_PATH = LOGS_DIR / "ide_awareness_runtime.jsonl"

IDE_INDICATORS = {
    "vscode_workspace": PROJECT_ROOT / ".vscode",
    "idea_workspace": PROJECT_ROOT / ".idea",
    "editorconfig": PROJECT_ROOT / ".editorconfig",
    "devcontainer": PROJECT_ROOT / ".devcontainer",
}


class IdeAwarenessRuntime:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        indicators = {
            name: {
                "path": str(path),
                "exists": path.exists(),
                "kind": "directory" if path.is_dir() else "file" if path.is_file() else "missing",
            }
            for name, path in IDE_INDICATORS.items()
        }

        terminal_hints = {
            "term_program": os.environ.get("TERM_PROGRAM"),
            "vscode_pid_present": bool(os.environ.get("VSCODE_PID")),
            "cursor_trace_present": bool(os.environ.get("CURSOR_TRACE_ID")),
            "shell": os.environ.get("SHELL") or os.environ.get("ComSpec"),
        }

        detected = [name for name, item in indicators.items() if item["exists"]]
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "ide_awareness_runtime",
            "bounded": True,
            "execution_allowed": False,
            "apply_allowed": False,
            "autonomous_apply": False,
            "dangerous_autonomous_apply": False,
            "human_approval_required": True,
            "awareness_mode": "safe_read_only_ide_observation",
            "phase": "phase_5_external_toolchain_runtime",
            "layer": "ide_awareness_runtime",
            "project_root": str(PROJECT_ROOT),
            "ide_indicators": indicators,
            "detected_indicators": detected,
            "terminal_hints": terminal_hints,
            "ide_awareness_state": "detected" if detected else "not_detected",
            "risk_signal": "low",
            "notes": [
                "IDE awareness is observation-only.",
                "No editor automation or file mutation was attempted.",
                "No autonomous execution capability is enabled.",
            ],
            "recommendation": "use_as_input_for_container_execution_awareness",
            "result": "ide_awareness_runtime_built",
        }

        OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.append_log(result)
        return result

    def append_log(self, result):
        entry = {
            "timestamp": result["timestamp"],
            "runtime": result["runtime"],
            "ide_awareness_state": result["ide_awareness_state"],
            "detected_indicators": result["detected_indicators"],
            "execution_allowed": False,
            "apply_allowed": False,
            "human_approval_required": True,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    print(json.dumps(IdeAwarenessRuntime().build(), ensure_ascii=False, indent=2))
