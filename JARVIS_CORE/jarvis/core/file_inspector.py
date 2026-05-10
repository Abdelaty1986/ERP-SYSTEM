from pathlib import Path


class FileInspector:
    MAX_PREVIEW_CHARS = 1200

    def __init__(self, root_path="."):
        self.root_path = Path(root_path)

    def inspect_file(self, file_path):
        path = self.root_path / file_path

        if not path.exists():
            return {
                "file": file_path,
                "exists": False,
                "type": "missing",
                "preview": None
            }

        if path.is_dir():
            return {
                "file": file_path,
                "exists": True,
                "type": "directory",
                "children": self._list_directory(path)
            }

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as error:
            return {
                "file": file_path,
                "exists": True,
                "type": "unreadable",
                "error": str(error)
            }

        return {
            "file": file_path,
            "exists": True,
            "type": "file",
            "size_chars": len(content),
            "preview": content[:self.MAX_PREVIEW_CHARS]
        }

    def inspect_many(self, file_paths):
        return [
            self.inspect_file(file_path)
            for file_path in file_paths
        ]

    def _list_directory(self, path):
        children = []

        for item in sorted(path.iterdir()):
            children.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file"
            })

            if len(children) >= 30:
                break

        return children


if __name__ == "__main__":
    inspector = FileInspector(".")

    results = inspector.inspect_many([
        "app.py",
        "templates/",
        "static/",
        "missing_file.py"
    ])

    for item in results:
        print(item)
        print("-" * 40)
