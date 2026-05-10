import json
from pathlib import Path


class ProjectLoader:
    def __init__(self, config_path="JARVIS_CORE/config/projects.json"):
        self.config_path = Path(config_path)

    def load_projects(self):
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Projects config not found: {self.config_path}"
            )

        with open(self.config_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        return data.get("projects", [])

    def get_project(self, project_id):
        projects = self.load_projects()

        for project in projects:
            if project["id"] == project_id:
                return project

        return None


if __name__ == "__main__":
    loader = ProjectLoader()

    projects = loader.load_projects()

    print("Loaded Projects:")
    for project in projects:
        print(
            f"- {project['name']} "
            f"({project['id']}) "
            f"[default: {project['default_branch']}]"
        )
