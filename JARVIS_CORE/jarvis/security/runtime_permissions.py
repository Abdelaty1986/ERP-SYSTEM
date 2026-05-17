from dataclasses import dataclass


@dataclass
class RuntimePermissionProfile:
    name: str
    allow_real_apply: bool
    allow_git_write: bool
    allow_branching: bool
    allow_shell_execution: bool


class RuntimePermissionManager:
    def __init__(self):
        self.profiles = {
            "readonly": RuntimePermissionProfile(
                name="readonly",
                allow_real_apply=False,
                allow_git_write=False,
                allow_branching=False,
                allow_shell_execution=False,
            ),
            "sandbox_only": RuntimePermissionProfile(
                name="sandbox_only",
                allow_real_apply=False,
                allow_git_write=False,
                allow_branching=True,
                allow_shell_execution=True,
            ),
            "gated_apply": RuntimePermissionProfile(
                name="gated_apply",
                allow_real_apply=True,
                allow_git_write=True,
                allow_branching=True,
                allow_shell_execution=True,
            ),
            "supervised": RuntimePermissionProfile(
                name="supervised",
                allow_real_apply=True,
                allow_git_write=True,
                allow_branching=True,
                allow_shell_execution=True,
            ),
        }

    def get_profile(self, permission_name):
        return self.profiles.get(
            permission_name,
            self.profiles["gated_apply"]
        )

    def validate_real_apply(self, permission_name):
        profile = self.get_profile(permission_name)
        return profile.allow_real_apply

    def validate_git_write(self, permission_name):
        profile = self.get_profile(permission_name)
        return profile.allow_git_write

    def validate_branching(self, permission_name):
        profile = self.get_profile(permission_name)
        return profile.allow_branching

    def validate_shell_execution(self, permission_name):
        profile = self.get_profile(permission_name)
        return profile.allow_shell_execution
