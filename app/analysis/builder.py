import ast
from pathlib import Path

from app.models.entity import FILE, Entity
from app.models.relationship import CONTAINS, Relationship
from app.models.unresolved import UnresolvedCall
from app.parser.entity_extractor import extract_entities
from app.parser.import_resolver import build_module_index, collect_import_bindings
from app.parser.call_resolver import _CallResolver
from app.parser.utils import normalize_file_path

def extract_contains_relationships(entities: list[Entity]) -> list[Relationship]:
    """CONTAINS: file → class/top-level function, class → method, function → nested def."""
    lookup = {entity.id: entity for entity in entities}
    files_by_path = {
        entity.file_path: entity
        for entity in entities
        if entity.entity_type == FILE
    }

    relationships: list[Relationship] = []
    seen: set[tuple[str, str, str]] = set()

    for entity in entities:
        if entity.entity_type == FILE:
            continue
        parent_id = entity.parent_id
        if parent_id is None or parent_id not in lookup:
            file_entity = files_by_path.get(entity.file_path)
            if file_entity is None:
                continue
            parent_id = file_entity.id
        key = (parent_id, entity.id, CONTAINS)
        if key in seen:
            continue
        seen.add(key)
        relationships.append(
            Relationship(
                source_id=parent_id,
                target_id=entity.id,
                relationship_type=CONTAINS,
            )
        )
    return relationships


def extract_relationships(
    tree: ast.AST,
    entities: list[Entity],
    file_path: Path | None = None,
    module_index: dict[str, Entity] | None = None,
) -> list[Relationship]:
    """
    Extract CONTAINS, IMPORTS, CALLS, and INSTANTIATES for one file.

    When file_path is omitted, the file is inferred from the FILE entity in
    `entities`. Pass the full repository entity list plus module_index so
    local imports and cross-file calls can be resolved.
    """
    if file_path is not None:
        path = normalize_file_path(file_path)
    else:
        file_entities = [entity for entity in entities if entity.entity_type == FILE]
        if not file_entities:
            return []
        path = file_entities[0].file_path

    if module_index is None:
        module_index = build_module_index(entities)

    relationships: list[Relationship] = []
    file_member_ids = {
        entity.id for entity in entities if entity.file_path == path
    }
    relationships.extend(
        rel
        for rel in extract_contains_relationships(entities)
        if rel.target_id in file_member_ids
    )

    import_result = collect_import_bindings(
        tree,
        path,
        entities,
        module_index,
    )
    relationships.extend(import_result.relationships)

    resolver = _CallResolver(
        path,
        entities,
        import_result.bindings,
        imported_modules=import_result.imported_modules,
        module_index=module_index,
    )
    resolver.visit(tree)
    relationships.extend(resolver.relationships)

    return relationships


def extract_repository_entities_and_relationships(
    parsed_files: list[tuple[str, ast.AST]],
) -> tuple[list[Entity], list[Relationship], list[UnresolvedCall]]:
    """
    Second-pass extraction over every parsed file in a repository.

    parsed_files: list of (repository-relative posix path, AST)
    """
    entities_by_id: dict[str, Entity] = {}

    for relative_path, tree in parsed_files:
        for entity in extract_entities(tree, Path(relative_path)):
            entities_by_id[entity.id] = entity

    entities = list(entities_by_id.values())
    module_index = build_module_index(entities)

    relationships: list[Relationship] = []
    unresolved: list[UnresolvedCall] = []
    seen: set[tuple[str, str, str]] = set()

    for rel in extract_contains_relationships(entities):
        key = (rel.source_id, rel.target_id, rel.relationship_type)
        if key not in seen:
            seen.add(key)
            relationships.append(rel)

    for relative_path, tree in parsed_files:
        import_result = collect_import_bindings(
            tree,
            relative_path,
            entities,
            module_index,
        )
        for rel in import_result.relationships:
            key = (rel.source_id, rel.target_id, rel.relationship_type)
            if key not in seen:
                seen.add(key)
                relationships.append(rel)

        resolver = _CallResolver(
            relative_path,
            entities,
            import_result.bindings,
            imported_modules=import_result.imported_modules,
            module_index=module_index,
        )
        resolver.visit(tree)
        for rel in resolver.relationships:
            key = (rel.source_id, rel.target_id, rel.relationship_type)
            if key not in seen:
                seen.add(key)
                relationships.append(rel)
        unresolved.extend(resolver.unresolved)

    return entities, relationships, unresolved
