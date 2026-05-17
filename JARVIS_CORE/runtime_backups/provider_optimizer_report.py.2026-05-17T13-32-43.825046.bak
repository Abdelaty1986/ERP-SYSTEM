import json
from pathlib import Path

from jarvis.runtime.provider_optimizer import ProviderOptimizer


class ProviderOptimizerReport:
    def __init__(self, report_path: str = "JARVIS_CORE/runtime_logs/provider_optimizer_report.json"):
        self.report_path = Path(report_path)
        self.report_path.parent.mkdir(parents=True, exist_ok=True)

    def generate(self):
        snapshot = ProviderOptimizer().snapshot()
        self.report_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return snapshot


if __name__ == "__main__":
    report = ProviderOptimizerReport().generate()
    print(json.dumps(report, ensure_ascii=False, indent=2))
