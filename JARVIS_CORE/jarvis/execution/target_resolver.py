from pathlib import Path


class TargetResolver:
    """
    Resolves broad or directory targets into real editable files.
    It does not modify files.
    """

    DEFAULT_CANDIDATES = [
        "app.py",
        "templates/base.html",
        "templates/dashboard.html",
        "templates/sales.html",
        "static/style.css",
        "static/css/ledgerx_enterprise_theme.css",
    ]

    def __init__(self, root="."):
        self.root = Path(root)

    def resolve_targets(self, expected_files):
        resolved = []
        skipped = []

        for item in expected_files:
            path = self.root / item

            if path.exists() and path.is_file():
                resolved.append(item)
                continue

            if path.exists() and path.is_dir():
                skipped.append({
                    "target": item,
                    "reason": "directory_target_skipped",
                })
                continue

            skipped.append({
                "target": item,
                "reason": "missing_target",
            })

        for candidate in self.DEFAULT_CANDIDATES:
            path = self.root / candidate

            if path.exists() and path.is_file() and candidate not in resolved:
                resolved.append(candidate)

        return {
            "status": "resolved",
            "resolved_targets": resolved,
            "skipped_targets": skipped,
            "resolved_count": len(resolved),
            "skipped_count": len(skipped),
        }
