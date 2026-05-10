from pathlib import Path


class ProjectScanner:
    IGNORED_DIRS = {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        "AI_SANDBOX",
        "backups",
        "instance"
    }

    IGNORED_PREFIXES = (
        "tmp",
        "erp-codex-test-",
        "erp-hr-test-",
        "erp-hr-ui-test-",
        "erp-hr-egypt-",
        "erp-hr-enterprise-",
        "erp-users-test-"
    )

    IMPORTANT_FILES = {
        "app.py",
        "requirements.txt",
        "Procfile",
        "nixpacks.toml",
        "README.md",
        "db.py",
        "migrations.py"
    }

    def __init__(self, root_path="."):
        self.root_path = Path(root_path)

    def scan(self):
        files = []
        important = []

        for path in self.root_path.rglob("*"):
            if self._is_ignored(path):
                continue

            if path.is_file():
                rel = str(path.relative_to(self.root_path))
                files.append(rel)

                if path.name in self.IMPORTANT_FILES:
                    important.append(rel)

        return {
            "root_path": str(self.root_path),
            "total_files": len(files),
            "important_files": sorted(important),
            "top_level_dirs": self._top_level_dirs(),
            "detected_stack": self._detect_stack(files)
        }

    def _is_ignored(self, path):
        for part in path.parts:
            if part in self.IGNORED_DIRS:
                return True

            if part.startswith(self.IGNORED_PREFIXES):
                return True

        return False

    def _top_level_dirs(self):
        dirs = []

        for item in self.root_path.iterdir():
            if not item.is_dir():
                continue

            if self._is_ignored(item):
                continue

            dirs.append(item.name)

        return sorted(dirs)

    def _detect_stack(self, files):
        stack = set()

        for file in files:
            if file.endswith(".py"):
                stack.add("python")
            if file.endswith(".html"):
                stack.add("html")
            if file.endswith(".css"):
                stack.add("css")
            if file.endswith(".js"):
                stack.add("javascript")
            if file.endswith(".db") or file.endswith(".sqlite"):
                stack.add("sqlite")

        return sorted(stack)


if __name__ == "__main__":
    scanner = ProjectScanner(".")
    result = scanner.scan()

    print("Project Scan Result")
    print("=" * 40)
    print(f"Total Files: {result['total_files']}")
    print(f"Detected Stack: {', '.join(result['detected_stack'])}")
    print(f"Top Level Dirs: {', '.join(result['top_level_dirs'])}")
    print("Important Files:")
    for file in result["important_files"]:
        print(f"- {file}")
