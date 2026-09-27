import ast
from pathlib import Path

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
