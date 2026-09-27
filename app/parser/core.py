import ast
from pathlib import Path

def parse_python_file(file_path: Path) -> ast.AST:
    """
    Parse a Python file and return its AST.
    """
    source_code = file_path.read_text(encoding="utf-8")
    return ast.parse(source_code, filename=str(file_path))
