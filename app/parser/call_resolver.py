import ast
from app.models.entity import CLASS, FILE, FUNCTION, Entity
from app.models.relationship import CALLS, INSTANTIATES, Relationship
from app.models.unresolved import UnresolvedCall
from app.parser.utils import _attribute_chain, _expr_text
from app.parser.import_resolver import (
    _classes_in_file,
    _function_entity_for_def,
    _functions_in_file,
    _methods_of_class,
)

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
