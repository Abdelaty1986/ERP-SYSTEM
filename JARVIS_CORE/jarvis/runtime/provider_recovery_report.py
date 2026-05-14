import json
from pathlib import Path

from jarvis.runtime.provider_recovery_planner import ProviderRecoveryPlanner


class ProviderRecoveryReport:
    def __init__(
        self,
        report_path: str = "JARVIS_CORE/runtime_logs/provider_recovery_report.json"
    ):
        self.report_path = Path(report_path)
        self.report_path.parent.mkdir(parents=True, exist_ok=True)

    def generate(self):
        snapshot = ProviderRecoveryPlanner().plan()

        self.report_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return snapshot


if __name__ == "__main__":
    report = ProviderRecoveryReport().generate()
    print(json.dumps(report, ensure_ascii=False, indent=2))
