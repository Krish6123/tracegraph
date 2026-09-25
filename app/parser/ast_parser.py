import ast
from pathlib import Path

from app.models.entity import Entity
from app.models.relationship import Relationship


def parse_python_file(file_path: Path) -> ast.AST:
    """
    Parse a Python file and return its AST.
    """

    source_code = file_path.read_text(encoding="utf-8")

    tree = ast.parse(
        source_code,
        filename=str(file_path)
    )

    return tree


def extract_entities(
    tree: ast.AST,
    file_path: Path,
    starting_id: int = 1
) -> list[Entity]:
    """
    Extract functions and classes from an AST.
    """

    entities = []
    next_id = starting_id

    for node in ast.walk(tree):

        if isinstance(node, ast.FunctionDef):
            entities.append(
                Entity(
                    id=next_id,
                    name=node.name,
                    entity_type="function",
                    file_path=str(file_path),
                    line_number=node.lineno,
                )
            )

            next_id += 1

        elif isinstance(node, ast.ClassDef):
            entities.append(
                Entity(
                    id=next_id,
                    name=node.name,
                    entity_type="class",
                    file_path=str(file_path),
                    line_number=node.lineno,
                )
            )

            next_id += 1

    return entities






def extract_relationships(
    tree: ast.AST,
    entities: list[Entity],
) -> list[Relationship]:
    """
    Extract relationships between entities.
    """

    relationships = []

    entity_by_name = {
        entity.name: entity
        for entity in entities
        if entity.entity_type == "function"
    }

    for node in ast.walk(tree):

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):

                called_name = node.func.id

                target_entity = entity_by_name.get(called_name)

                if target_entity is not None:

                    source_entity = None

                    for entity in entities:
                        if (
                            entity.entity_type == "function"
                            and entity.line_number <= node.lineno
                        ):
                            source_entity = entity

                    if source_entity is not None:
                        relationships.append(
                            Relationship(
                                source_id=source_entity.id,
                                target_id=target_entity.id,
                                relationship_type="CALLS",
                            )
                        )

    return relationships
