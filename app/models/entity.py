from dataclasses import dataclass


FILE = "file"
FUNCTION = "function"
CLASS = "class"


@dataclass(frozen=True)
class Entity:
    id: str
    name: str
    entity_type: str
    file_path: str
    line_number: int


def make_entity_id(
    entity_type: str,
    file_path: str,
    name: str | None = None,
    line_number: int | None = None,
) -> str:
    """
    Build a unique, stable entity ID from repository-relative path and location.

    The same file/function/class always produces the same ID, independent of
    scan order. Integer counters are intentionally not used.
    """
    if entity_type == FILE:
        return f"file:{file_path}"

    return f"{entity_type}:{file_path}:{name}:{line_number}"
