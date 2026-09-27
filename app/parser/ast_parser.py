import ast
from dataclasses import dataclass, field
from pathlib import Path

from app.models.entity import (
    CLASS,
    FILE,
    FUNCTION,
    Entity,
    make_entity_id,
)
from app.models.relationship import (
    CALLS,
    CONTAINS,
    IMPORTS,
    INSTANTIATES,
    Relationship,
)


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
        payment.py                -> payment
        services/payment_service.py -> services.payment_service
        pkg/__init__.py           -> pkg
    """
    path = Path(relative_path)
    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _expr_text(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return "<expr>"


@dataclass(frozen=True)
class UnresolvedCall:
    file_path: str
    line_number: int
    expression: str
    reason: str


class _EntityExtractor(ast.NodeVisitor):
    """Walk one file, recording FILE / CLASS / FUNCTION with parent links."""

    def __init__(self, path: str) -> None:
        self.path = path
        file_entity = Entity(
            id=make_entity_id(FILE, path),
            name=Path(path).name,
            entity_type=FILE,
            file_path=path,
            line_number=1,
        )
        self.entities: dict[str, Entity] = {file_entity.id: file_entity}
        self.file_entity = file_entity
        self.class_stack: list[Entity] = []
        self.function_stack: list[Entity] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        parent = self._current_parent()
        entity = Entity(
            id=make_entity_id(CLASS, self.path, node.name, node.lineno),
            name=node.name,
            entity_type=CLASS,
            file_path=self.path,
            line_number=node.lineno,
            parent_id=parent.id,
        )
        self.entities[entity.id] = entity
        self.class_stack.append(entity)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        is_method = bool(self.class_stack) and not self.function_stack
        if is_method:
            class_entity = self.class_stack[-1]
            name = f"{class_entity.name}.{node.name}"
            parent = class_entity
        else:
            name = node.name
            parent = self._current_parent()

        entity = Entity(
            id=make_entity_id(FUNCTION, self.path, name, node.lineno),
            name=name,
            entity_type=FUNCTION,
            file_path=self.path,
            line_number=node.lineno,
            parent_id=parent.id,
        )
        self.entities[entity.id] = entity
        self.function_stack.append(entity)
        self.generic_visit(node)
        self.function_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def _current_parent(self) -> Entity:
        if self.function_stack:
            return self.function_stack[-1]
        if self.class_stack:
            return self.class_stack[-1]
        return self.file_entity


def extract_entities(
    tree: ast.AST,
    file_path: Path,
    starting_id: int = 1,
) -> list[Entity]:
    """
    Extract FILE, FUNCTION, and CLASS entities from one AST.

    Methods keep entity_type FUNCTION and use a qualified name
    (PaymentService.process). Nested functions are parented to the
    enclosing function, not treated as file-level.

    starting_id is accepted for compatibility with the earlier integer-ID
    extractor; IDs are now stable strings and the argument is ignored.
    """
    del starting_id
    extractor = _EntityExtractor(normalize_file_path(file_path))
    extractor.visit(tree)
    return list(extractor.entities.values())


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


def _attribute_chain(node: ast.AST) -> list[str] | None:
    """Turn Name / Attribute into ['services', 'payment_service', 'process']."""
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        parts.reverse()
        return parts
    return None


class _CallResolver(ast.NodeVisitor):
    """Walk an AST, tracking the enclosing function/class, and resolve calls."""

    def __init__(
        self,
        file_path: str,
        entities: list[Entity],
        bindings: dict[str, tuple[str, Entity]],
        imported_modules: set[str] | None = None,
        module_index: dict[str, Entity] | None = None,
    ):
        self.file_path = file_path
        self.entities = entities
        self.bindings = bindings
        self.imported_modules = imported_modules or set()
        self.module_index = module_index or {}
        self.local_functions = _functions_in_file(entities, file_path)
        self.local_classes = _classes_in_file(entities, file_path)
        self.function_stack: list[Entity] = []
        self.class_stack: list[Entity] = []
        self.scope_stack: list[dict[str, tuple[str, Entity] | None]] = [{}]
        self.relationships: list[Relationship] = []
        self.unresolved: list[UnresolvedCall] = []
        self._seen: set[tuple[str, str, str]] = set()
        self._local_method_names = {
            entity.name.split(".")[-1]
            for entity in entities
            if entity.entity_type == FUNCTION and "." in entity.name
        }
        self._local_function_names = {
            entity.name
            for entity in entities
            if entity.entity_type == FUNCTION and "." not in entity.name
        }

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        class_entity = None
        for entity in self.entities:
            if (
                entity.entity_type == CLASS
                and entity.file_path == self.file_path
                and entity.name == node.name
                and entity.line_number == node.lineno
            ):
                class_entity = entity
                break
        if class_entity is not None:
            self.class_stack.append(class_entity)
        self.generic_visit(node)
        if class_entity is not None:
            self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        entity = _function_entity_for_def(
            self.entities,
            self.file_path,
            node,
            self.class_stack,
            self.function_stack,
        )
        self.scope_stack.append({})
        if entity is not None:
            self.function_stack.append(entity)
        self.generic_visit(node)
        if entity is not None:
            self.function_stack.pop()
        self.scope_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Assign(self, node: ast.Assign) -> None:
        self.generic_visit(node)
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            self._bind_name(node.targets[0].id, node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.generic_visit(node)
        if isinstance(node.target, ast.Name) and node.value is not None:
            self._bind_name(node.target.id, node.value)

    def visit_Call(self, node: ast.Call) -> None:
        target = self._resolve_callee(node.func)
        if self.function_stack:
            source = self.function_stack[-1]
            if target is not None and target.entity_type == FUNCTION:
                self._add_edge(source.id, target.id, CALLS)
            elif target is not None and target.entity_type == CLASS:
                self._add_edge(source.id, target.id, INSTANTIATES)
            elif target is None:
                self._maybe_record_unresolved(node)
        self.generic_visit(node)

    def _add_edge(self, source_id: str, target_id: str, rel_type: str) -> None:
        key = (source_id, target_id, rel_type)
        if key in self._seen:
            return
        self._seen.add(key)
        self.relationships.append(
            Relationship(
                source_id=source_id,
                target_id=target_id,
                relationship_type=rel_type,
            )
        )

    def _bind_name(self, name: str, value: ast.AST) -> None:
        entity = (
            self._resolve_callee(value.func)
            if isinstance(value, ast.Call)
            else None
        )
        if entity is None and isinstance(value, ast.Name):
            entity = self._lookup_name(value.id)
        if entity is not None and entity.entity_type == CLASS:
            self.scope_stack[-1][name] = ("class", entity)
        elif entity is not None and entity.entity_type == FILE:
            self.scope_stack[-1][name] = ("module", entity)
        else:
            self.scope_stack[-1][name] = None

    def _lookup_name(self, name: str) -> Entity | None:
        for scope in reversed(self.scope_stack):
            if name in scope:
                binding = scope[name]
                if binding is None:
                    return None
                return binding[1]
        if name in self.local_classes:
            return self.local_classes[name]
        binding = self.bindings.get(name)
        if binding is not None and binding[0] in {"class", "function", "module"}:
            return binding[1]
        if name in self.local_functions:
            return self.local_functions[name]
        return None

    def _lookup_typed(self, name: str) -> tuple[str, Entity] | None:
        for scope in reversed(self.scope_stack):
            if name in scope:
                return scope[name]
        if name in self.local_classes:
            return ("class", self.local_classes[name])
        binding = self.bindings.get(name)
        if binding is not None and binding[0] in {"class", "function", "module"}:
            return binding
        return None

    def _resolve_callee(self, func: ast.AST) -> Entity | None:
        # process_payment()  /  PaymentService()
        if isinstance(func, ast.Name):
            name = func.id
            if name in self.local_functions:
                return self.local_functions[name]
            typed = self._lookup_typed(name)
            if typed is not None:
                return typed[1]
            binding = self.bindings.get(name)
            if binding is not None and binding[0] in {"function", "class"}:
                return binding[1]
            if name in self.local_classes:
                return self.local_classes[name]
            return None

        chain = _attribute_chain(func)
        if not chain or len(chain) < 2:
            return None

        # PaymentService.process  /  service.process  /  module.func
        if len(chain) == 2:
            return self._resolve_obj_attr(chain[0], chain[1])

        # import pkg.mod; pkg.mod.func()
        module_name = ".".join(chain[:-1])
        attr = chain[-1]
        if module_name in self.imported_modules:
            module_file = self.module_index.get(module_name)
            if module_file is None:
                return None
            functions = _functions_in_file(self.entities, module_file.file_path)
            if attr in functions:
                return functions[attr]
            classes = _classes_in_file(self.entities, module_file.file_path)
            return classes.get(attr)

        return None

    def _resolve_obj_attr(self, base: str, attr: str) -> Entity | None:
        if base == "self" and self.class_stack:
            methods = _methods_of_class(self.entities, self.class_stack[-1])
            return methods.get(attr)

        typed = self._lookup_typed(base)
        if typed is None:
            return None
        kind, entity = typed
        if kind == "class":
            methods = _methods_of_class(self.entities, entity)
            if attr in methods:
                return methods[attr]
            # Class attribute that is not a method is unresolved; do not guess.
            return None
        if kind == "module":
            functions = _functions_in_file(self.entities, entity.file_path)
            if attr in functions:
                return functions[attr]
            classes = _classes_in_file(self.entities, entity.file_path)
            return classes.get(attr)
        return None

    def _maybe_record_unresolved(self, node: ast.Call) -> None:
        chain = _attribute_chain(node.func)
        if chain is None or len(chain) < 2:
            return
        attr = chain[-1]
        local_hit = attr in self._local_method_names or attr in self._local_function_names
        if not local_hit:
            return
        self.unresolved.append(
            UnresolvedCall(
                file_path=self.file_path,
                line_number=getattr(node, "lineno", 1),
                expression=_expr_text(node.func),
                reason=(
                    "receiver type unknown; not guessing among local "
                    f"functions/methods named {attr!r}"
                ),
            )
        )


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
