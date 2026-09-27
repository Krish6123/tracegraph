from dataclasses import dataclass


CONTAINS = "CONTAINS"
IMPORTS = "IMPORTS"
CALLS = "CALLS"
INSTANTIATES = "INSTANTIATES"


@dataclass(frozen=True)
class Relationship:
    source_id: str
    target_id: str
    relationship_type: str
