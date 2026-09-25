import ast
from pathlib import Path

from app.models.entity import (
    CLASS,
    FILE,
    FUNCTION,
    Entity,
    make_entity_id,
)
from app.models.relationship import CALLS, CONTAINS, IMPORTS, Relationship


def parse_python_file(file_path: Path) -> ast.AST:
    """
    Parse a Python file and return its AST.
    """
    source_code = file_path.read_text(encoding="utf-8")
    return ast.parse(source_code, filename=str(file_path))


def normalize_file_path(file_path: Path) -> str:
    """Store paths in a stable, OS-independent form."""
    return Path(file_path).as_posix()


def module_name_from_relative_path(relative_path: str) -> str:
    """
    Map a repository-relative Python file to a dotted module name.

    examples:
        payment.py          -> payment
        pkg/mod.py          -> pkg.mod
        pkg/__init__.py     -> pkg
    """
    path = Path(relative_path)
    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def extract_entities(
    tree: ast.AST,
    file_path: Path,
    starting_id: int = 1,
) -> list[Entity]:
    """
    Extract FILE, FUNCTION, and CLASS entities from one AST.

    starting_id is accepted for compatibility with the earlier integer-ID
    extractor; IDs are now stable strings and the argument is ignored.
    """
    del starting_id

    path = normalize_file_path(file_path)
    entities: dict[str, Entity] = {}

    file_entity = Entity(
        id=make_entity_id(FILE, path),
        name=Path(path).name,
        entity_type=FILE,
        file_path=path,
        line_number=1,
    )
    entities[file_entity.id] = file_entity

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            entity = Entity(
                id=make_entity_id(FUNCTION, path, node.name, node.lineno),
                name=node.name,
                entity_type=FUNCTION,
                file_path=path,
                line_number=node.lineno,
            )
            entities[entity.id] = entity
        elif isinstance(node, ast.ClassDef):
            entity = Entity(
                id=make_entity_id(CLASS, path, node.name, node.lineno),
                name=node.name,
                entity_type=CLASS,
                file_path=path,
                line_number=node.lineno,
            )
            entities[entity.id] = entity

    return list(entities.values())


def _entity_lookup(entities: list[Entity]) -> dict[str, Entity]:
    return {entity.id: entity for entity in entities}


def _file_entity(entities: list[Entity], file_path: str) -> Entity | None:
    file_id = make_entity_id(FILE, file_path)
    for entity in entities:
        if entity.id == file_id:
            return entity
    return None


def _functions_in_file(entities: list[Entity], file_path: str) -> dict[str, Entity]:
    """Index top-level-looking functions by name for call/import resolution.

    If two functions in the same file share a name (e.g. nested defs), the
    earliest line number is used. Nested same-name functions are a known
    resolution limitation.
    """
    indexed: dict[str, Entity] = {}
    for entity in entities:
        if entity.entity_type == FUNCTION and entity.file_path == file_path:
            existing = indexed.get(entity.name)
            if existing is None or entity.line_number < existing.line_number:
                indexed[entity.name] = entity
    return indexed


def _classes_in_file(entities: list[Entity], file_path: str) -> dict[str, Entity]:
    indexed: dict[str, Entity] = {}
    for entity in entities:
        if entity.entity_type == CLASS and entity.file_path == file_path:
            existing = indexed.get(entity.name)
            if existing is None or entity.line_number < existing.line_number:
                indexed[entity.name] = entity
    return indexed


def _function_by_location(
    entities: list[Entity],
    file_path: str,
    name: str,
    line_number: int,
) -> Entity | None:
    entity_id = make_entity_id(FUNCTION, file_path, name, line_number)
    lookup = _entity_lookup(entities)
    return lookup.get(entity_id)


def build_module_index(entities: list[Entity]) -> dict[str, Entity]:
    """Map dotted module names to FILE entities in the analyzed repository."""
    index: dict[str, Entity] = {}
    for entity in entities:
        if entity.entity_type != FILE:
            continue
        module_name = module_name_from_relative_path(entity.file_path)
        if module_name:
            index[module_name] = entity
    return index


def collect_import_bindings(
    tree: ast.AST,
    file_path: str,
    entities: list[Entity],
    module_index: dict[str, Entity],
) -> tuple[list[Relationship], dict[str, tuple[str, Entity]]]:
    """
    Resolve simple local imports and return IMPORTS edges plus name bindings.

    Bindings map a local name to ("module", file_entity) or
    ("function"|"class", entity). Relative imports and unresolved third-party
    / stdlib modules are skipped.
    """
    relationships: list[Relationship] = []
    bindings: dict[str, tuple[str, Entity]] = {}
    seen_edges: set[tuple[str, str, str]] = set()

    source_file = _file_entity(entities, file_path)
    if source_file is None:
        return relationships, bindings

    def add_imports_edge(target_file: Entity) -> None:
        key = (source_file.id, target_file.id, IMPORTS)
        if key in seen_edges:
            return
        seen_edges.add(key)
        relationships.append(
            Relationship(
                source_id=source_file.id,
                target_id=target_file.id,
                relationship_type=IMPORTS,
            )
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # Only simple `import module` names are resolved.
                # `import pkg.sub` is attempted as a full dotted name.
                target_file = module_index.get(alias.name)
                if target_file is None:
                    continue
                add_imports_edge(target_file)
                local_name = alias.asname or alias.name.split(".")[0]
                bindings[local_name] = ("module", target_file)

        elif isinstance(node, ast.ImportFrom):
            # Relative imports (from . import x / from ..pkg import y) are not resolved.
            if node.level and node.level > 0:
                continue
            if not node.module:
                continue

            target_file = module_index.get(node.module)
            if target_file is None:
                continue

            add_imports_edge(target_file)
            target_functions = _functions_in_file(entities, target_file.file_path)
            target_classes = _classes_in_file(entities, target_file.file_path)

            for alias in node.names:
                if alias.name == "*":
                    for name, func in target_functions.items():
                        bindings[name] = ("function", func)
                    for name, cls in target_classes.items():
                        bindings[name] = ("class", cls)
                    continue

                local_name = alias.asname or alias.name
                if alias.name in target_functions:
                    bindings[local_name] = ("function", target_functions[alias.name])
                elif alias.name in target_classes:
                    bindings[local_name] = ("class", target_classes[alias.name])
                else:
                    bindings[local_name] = ("unknown", target_file)

    return relationships, bindings


class _CallResolver(ast.NodeVisitor):
    """Walk an AST, tracking the enclosing function, and resolve simple calls."""

    def __init__(
        self,
        file_path: str,
        entities: list[Entity],
        bindings: dict[str, tuple[str, Entity]],
    ):
        self.file_path = file_path
        self.entities = entities
        self.bindings = bindings
        self.local_functions = _functions_in_file(entities, file_path)
        self.function_stack: list[Entity] = []
        self.relationships: list[Relationship] = []
        self._seen: set[tuple[str, str, str]] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        entity = _function_by_location(
            self.entities,
            self.file_path,
            node.name,
            node.lineno,
        )
        if entity is not None:
            self.function_stack.append(entity)
        self.generic_visit(node)
        if entity is not None:
            self.function_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        if self.function_stack:
            source = self.function_stack[-1]
            target = self._resolve_callee(node.func)
            if target is not None and target.entity_type == FUNCTION:
                key = (source.id, target.id, CALLS)
                if key not in self._seen:
                    self._seen.add(key)
                    self.relationships.append(
                        Relationship(
                            source_id=source.id,
                            target_id=target.id,
                            relationship_type=CALLS,
                        )
                    )
        self.generic_visit(node)

    def _resolve_callee(self, func: ast.AST) -> Entity | None:
        # process_payment()
        if isinstance(func, ast.Name):
            name = func.id
            if name in self.local_functions:
                return self.local_functions[name]
            binding = self.bindings.get(name)
            if binding is not None and binding[0] in {"function", "class"}:
                return binding[1]
            return None

        # payment.process_payment()
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            base = func.value.id
            attr = func.attr
            binding = self.bindings.get(base)
            if binding is None or binding[0] != "module":
                return None
            module_file = binding[1]
            functions = _functions_in_file(self.entities, module_file.file_path)
            return functions.get(attr)

        return None


def extract_contains_relationships(entities: list[Entity]) -> list[Relationship]:
    """CONTAINS: file → function/class."""
    relationships: list[Relationship] = []
    files_by_path = {
        entity.file_path: entity
        for entity in entities
        if entity.entity_type == FILE
    }

    seen: set[tuple[str, str, str]] = set()
    for entity in entities:
        if entity.entity_type not in {FUNCTION, CLASS}:
            continue
        file_entity = files_by_path.get(entity.file_path)
        if file_entity is None:
            continue
        key = (file_entity.id, entity.id, CONTAINS)
        if key in seen:
            continue
        seen.add(key)
        relationships.append(
            Relationship(
                source_id=file_entity.id,
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
    Extract CONTAINS, IMPORTS, and CALLS relationships for one file.

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
    file_entities = [
        entity
        for entity in entities
        if entity.entity_type == FILE and entity.file_path == path
    ]
    # CONTAINS only for this file's members; IMPORTS/CALLS need the full set.
    relationships.extend(
        rel
        for rel in extract_contains_relationships(entities)
        if file_entities and rel.source_id == file_entities[0].id
    )

    import_rels, bindings = collect_import_bindings(
        tree,
        path,
        entities,
        module_index,
    )
    relationships.extend(import_rels)

    resolver = _CallResolver(path, entities, bindings)
    resolver.visit(tree)
    relationships.extend(resolver.relationships)

    return relationships


def extract_repository_entities_and_relationships(
    parsed_files: list[tuple[str, ast.AST]],
) -> tuple[list[Entity], list[Relationship]]:
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
    seen: set[tuple[str, str, str]] = set()

    for rel in extract_contains_relationships(entities):
        key = (rel.source_id, rel.target_id, rel.relationship_type)
        if key not in seen:
            seen.add(key)
            relationships.append(rel)

    for relative_path, tree in parsed_files:
        import_rels, bindings = collect_import_bindings(
            tree,
            relative_path,
            entities,
            module_index,
        )
        for rel in import_rels:
            key = (rel.source_id, rel.target_id, rel.relationship_type)
            if key not in seen:
                seen.add(key)
                relationships.append(rel)

        resolver = _CallResolver(relative_path, entities, bindings)
        resolver.visit(tree)
        for rel in resolver.relationships:
            key = (rel.source_id, rel.target_id, rel.relationship_type)
            if key not in seen:
                seen.add(key)
                relationships.append(rel)

    return entities, relationships
