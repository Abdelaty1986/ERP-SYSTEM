from pathlib import Path
import shutil


class RealApplyApplier:
    """
    Applies staged sandbox-approved files to real project targets.
    This engine must NEVER run unless policy manager allows it.
    """

    def __init__(self, root="."):
        self.root = Path(root).resolve()

    def apply(
        self,
        policy_result,
        staged_files,
    ):
        if not policy_result.get("ok"):
            return {
                "status": "blocked",
                "ok": False,
                "reason": policy_result.get("reason"),
                "applied_files": [],
            }

        applied = []
        failed = []

        for item in staged_files:
            if isinstance(item, str):
                source = item
                target = item
            else:
                source = item.get("staged")
                target = item.get("target") or item.get("file") or item.get("source")

            if not source or not target:
                failed.append({
                    "target": target,
                    "reason": "missing_source_or_target"
                })
                continue

            source_path = Path(source).resolve()
            target_path = (self.root / target).resolve()

            try:
                target_path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                shutil.copy2(source_path, target_path)

                applied.append({
                    "target": target,
                    "source": source,
                    "status": "applied"
                })

            except Exception as exc:
                failed.append({
                    "target": target,
                    "reason": str(exc)
                })

        return {
            "status": (
                "applied"
                if not failed
                else "partial_failure"
            ),
            "ok": len(failed) == 0,
            "applied_files": applied,
            "failed_files": failed,
        }
