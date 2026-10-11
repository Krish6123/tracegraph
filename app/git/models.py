from enum import Enum
from dataclasses import dataclass


class ChangeType(Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass
class FileChange:
    change_type: ChangeType
    path: str
    old_path: str | None = None
