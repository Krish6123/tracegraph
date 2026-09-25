from dataclasses import dataclass


@dataclass
class Entity:
    id: int
    name: str
    entity_type: str
    file_path: str
    line_number: int