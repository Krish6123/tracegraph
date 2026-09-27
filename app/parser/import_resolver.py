import ast
from dataclasses import dataclass, field

from app.models.entity import CLASS, FILE, FUNCTION, Entity, make_entity_id
from app.models.relationship import IMPORTS, Relationship
from app.parser.utils import module_name_from_relative_path

def _entity_lookup(entities: list[Entity]) -> dict[str, Entity]:
    return {entity.id: entity for entity in entities}


def _file_entity(entities: list[Entity], file_path: str) -> Entity | None:
    file_id = make_entity_id(FILE, file_path)
    for entity in entities:
        if entity.id == file_id:
            return entity
    return None


def _top_level_functions_in_file(
    entities: list[Entity], file_path: str
) -> dict[str, Entity]:
    """Index functions whose parent is the file (not methods / nested defs)."""
    file_id = make_entity_id(FILE, file_path)
    indexed: dict[str, Entity] = {}
    for entity in entities:
        if entity.entity_type != FUNCTION or entity.file_path != file_path:
            continue
        if entity.parent_id != file_id:
            continue
        existing = indexed.get(entity.name)
        if existing is None or entity.line_number < existing.line_number:
            indexed[entity.name] = entity
    return indexed


def _functions_in_file(entities: list[Entity], file_path: str) -> dict[str, Entity]:
    """
    Index top-level functions by name for import/call resolution.

    Methods use qualified names and are excluded. Nested same-name
    functions remain a known limitation of name-based lookup.
    """
    return _top_level_functions_in_file(entities, file_path)


def _classes_in_file(entities: list[Entity], file_path: str) -> dict[str, Entity]:
    file_id = make_entity_id(FILE, file_path)
    indexed: dict[str, Entity] = {}
    for entity in entities:
        if entity.entity_type != CLASS or entity.file_path != file_path:
            continue
        if entity.parent_id not in {file_id, None}:
            continue
        existing = indexed.get(entity.name)
        if existing is None or entity.line_number < existing.line_number:
            indexed[entity.name] = entity
    return indexed


def _methods_of_class(
    entities: list[Entity], class_entity: Entity
) -> dict[str, Entity]:
    """Map simple method name (process) → entity named Class.process."""
    indexed: dict[str, Entity] = {}
    prefix = f"{class_entity.name}."
    for entity in entities:
        if entity.entity_type != FUNCTION:
            continue
        if entity.parent_id != class_entity.id:
            continue
        simple = entity.name[len(prefix) :] if entity.name.startswith(prefix) else entity.name
        existing = indexed.get(simple)
        if existing is None or entity.line_number < existing.line_number:
            indexed[simple] = entity
    return indexed


def _function_by_location(
    entities: list[Entity],
    file_path: str,
    name: str,
    line_number: int,
) -> Entity | None:
    lookup = _entity_lookup(entities)
    entity_id = make_entity_id(FUNCTION, file_path, name, line_number)
    return lookup.get(entity_id)


def _function_entity_for_def(
    entities: list[Entity],
    file_path: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    class_stack: list[Entity],
    function_stack: list[Entity],
) -> Entity | None:
    is_method = bool(class_stack) and not function_stack
    if is_method:
        name = f"{class_stack[-1].name}.{node.name}"
    else:
        name = node.name
    return _function_by_location(entities, file_path, name, node.lineno)


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


@dataclass
class ImportResolution:
    relationships: list[Relationship]
    bindings: dict[str, tuple[str, Entity]]
    imported_modules: set[str] = field(default_factory=set)


def collect_import_bindings(
    tree: ast.AST,
    file_path: str,
    entities: list[Entity],
    module_index: dict[str, Entity],
) -> ImportResolution:
    """
    Resolve simple local imports, including nested packages and aliases.

    Bindings map a local name to ("module", file_entity) or
    ("function"|"class", entity). Relative imports and unresolved third-party
    / stdlib modules are skipped — no relationship is created without a
    local file/entity target.
    """
    relationships: list[Relationship] = []
    bindings: dict[str, tuple[str, Entity]] = {}
    imported_modules: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()

    source_file = _file_entity(entities, file_path)
    if source_file is None:
        return ImportResolution(relationships, bindings, imported_modules)

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
                target_file = module_index.get(alias.name)
                if target_file is None:
                    continue
                add_imports_edge(target_file)
                imported_modules.add(alias.name)
                if alias.asname:
                    bindings[alias.asname] = ("module", target_file)
                elif "." not in alias.name:
                    bindings[alias.name] = ("module", target_file)
                # Unaliased `import pkg.mod` does not bind a simple name
                # to the leaf module (Python binds the top package).

        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue
            if not node.module:
                continue

            package_file = module_index.get(node.module)
            target_functions = (
                _functions_in_file(entities, package_file.file_path)
                if package_file is not None
                else {}
            )
            target_classes = (
                _classes_in_file(entities, package_file.file_path)
                if package_file is not None
                else {}
            )

            module_imported = False

            for alias in node.names:
                if alias.name == "*":
                    if package_file is None:
                        continue
                    if not module_imported:
                        add_imports_edge(package_file)
                        imported_modules.add(node.module)
                        module_imported = True
                    for name, func in target_functions.items():
                        bindings[name] = ("function", func)
                    for name, cls in target_classes.items():
                        bindings[name] = ("class", cls)
                    continue

                local_name = alias.asname or alias.name
                submodule_name = f"{node.module}.{alias.name}"
                submodule_file = module_index.get(submodule_name)

                if submodule_file is not None:
                    add_imports_edge(submodule_file)
                    imported_modules.add(submodule_name)
                    bindings[local_name] = ("module", submodule_file)
                    continue

                if package_file is None:
                    continue

                if not module_imported:
                    add_imports_edge(package_file)
                    imported_modules.add(node.module)
                    module_imported = True

                if alias.name in target_functions:
                    bindings[local_name] = ("function", target_functions[alias.name])
                elif alias.name in target_classes:
                    bindings[local_name] = ("class", target_classes[alias.name])
                else:
                    bindings[local_name] = ("unknown", package_file)

    return ImportResolution(relationships, bindings, imported_modules)
