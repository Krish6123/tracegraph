from dataclasses import dataclass


@dataclass
class Relationship:
    source_id: int
    target_id: int
    relationship_type: str