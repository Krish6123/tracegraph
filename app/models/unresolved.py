from dataclasses import dataclass

@dataclass(frozen=True)
class UnresolvedCall:
    file_path: str
    line_number: int
    expression: str
    reason: str
