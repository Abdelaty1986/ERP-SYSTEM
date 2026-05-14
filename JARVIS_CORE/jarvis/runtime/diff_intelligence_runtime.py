import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "runtime_memory"
DIFF_PATH = MEMORY_DIR / "diff_intelligence_runtime.json"


class DiffIntelligenceRuntime:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    def run_git(self, args):
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=ROOT.parent,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return {
                "ok": result.returncode == 0,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            }
        except Exception as exc:
            return {
                "ok": False,
                "stdout": "",
                "stderr": str(exc),
            }

    def analyze(self):
        status = self.run_git(["status", "--short"])
        diff_stat = self.run_git(["diff", "--stat"])
        staged_stat = self.run_git(["diff", "--cached", "--stat"])

        changed_lines = status["stdout"].splitlines() if status["stdout"] else []

        files = []
        for line in changed_lines:
            parts = line.strip().split(maxsplit=1)
            if len(parts) == 2:
                files.append({
                    "state": parts[0],
                    "path": parts[1],
                })

        risk = "clean"
        if files:
            risky = [
                f for f in files
                if f["path"].startswith("JARVIS_CORE/runtime_memory/")
                or f["path"].startswith("JARVIS_CORE/runtime_logs/")
            ]
            risk = "runtime_memory_changed" if risky else "code_changed"

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "diff_intelligence_runtime",
            "bounded": True,
            "dangerous_autonomous_apply": False,
            "analysis_mode": "safe_read_only_git_diff_analysis",
            "working_tree_clean": len(files) == 0,
            "changed_file_count": len(files),
            "changed_files": files,
            "diff_stat": diff_stat,
            "staged_diff_stat": staged_stat,
            "risk_state": risk,
            "recommendation": (
                "safe_to_continue"
                if len(files) == 0
                else "review_changes_before_next_layer"
            ),
            "result": "diff_intelligence_built",
        }

        DIFF_PATH.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return result


if __name__ == "__main__":
    result = DiffIntelligenceRuntime().analyze()
    print(json.dumps(result, ensure_ascii=False, indent=2))
