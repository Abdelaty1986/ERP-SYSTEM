from datetime import datetime
import uuid


class ApplySession:
    def __init__(self, task):
        self.session_id = str(uuid.uuid4())
        self.task = task

        self.created_at = datetime.utcnow().isoformat()

        self.status = "initialized"

        self.backups = []

        self.staged_files = []

        self.skipped_targets = []

        self.validation_passed = False

        self.approval_received = False

        self.tests_passed = False

    def add_backup(self, backup_data):
        self.backups.append(backup_data)

    def add_staged_file(self, staged_data):
        self.staged_files.append(staged_data)

    def add_skipped_target(self, target_data):
        self.skipped_targets.append(target_data)

    def mark_validation_passed(self):
        self.validation_passed = True

    def mark_approval_received(self):
        self.approval_received = True

    def mark_tests_passed(self):
        self.tests_passed = True

    def set_status(self, status):
        self.status = status

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "task": self.task,
            "created_at": self.created_at,
            "status": self.status,
            "validation_passed": self.validation_passed,
            "approval_received": self.approval_received,
            "tests_passed": self.tests_passed,
            "backups": self.backups,
            "staged_files": self.staged_files,
            "skipped_targets": self.skipped_targets,
        }
