import json
from pathlib import Path

from jarvis.runtime.provider_recovery_executor import ProviderRecoveryExecutor


class ProviderRecoveryExecutorReport:
    def __init__(
        self,
        report_path: str = "JARVIS_CORE/runtime_logs/provider_recovery_executor_report.json"
    ):
        self.report_path = Path(report_path)
        self.report_path.parent.mkdir(parents=True, exist_ok=True)

    def generate(self, dry_run: bool = True):
        snapshot = ProviderRecoveryExecutor().execute(dry_run=dry_run)

        self.report_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return snapshot


if __name__ == "__main__":
    report = ProviderRecoveryExecutorReport().generate(dry_run=True)
    print(json.dumps(report, ensure_ascii=False, indent=2))
