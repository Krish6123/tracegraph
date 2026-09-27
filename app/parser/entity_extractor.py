import ast
from pathlib import Path

from app.models.entity import CLASS, FILE, FUNCTION, Entity, make_entity_id
from app.parser.utils import normalize_file_path

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
