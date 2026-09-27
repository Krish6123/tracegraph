from pathlib import Path


# Skip generated / environment trees so nested package scans stay on source.
_SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    ".tox",
    "site-packages",
}


def _is_skipped(path: Path) -> bool:
    return any(part in _SKIP_DIR_NAMES for part in path.parts)


def find_python_files(repository_path: str) -> list[Path]:
    """
    Find all Python files inside a repository (nested packages included).
    """

    repository = Path(repository_path)

    if not repository.exists():
        raise FileNotFoundError(
            f"Repository does not exist: {repository}"
        )

    if not repository.is_dir():
        raise NotADirectoryError(
            f"Path is not a directory: {repository}"
        )

    python_files = [
        path
        for path in repository.rglob("*.py")
        if not _is_skipped(path)
    ]

    return sorted(python_files)


def relative_python_paths(repository_path: str) -> list[str]:
    """Repository-relative posix paths for every scanned Python file."""
    repository = Path(repository_path).resolve()
    paths: list[str] = []
    for file_path in find_python_files(repository_path):
        try:
            relative = file_path.resolve().relative_to(repository).as_posix()
        except ValueError:
            relative = file_path.as_posix()
        paths.append(relative)
    return paths


def find_python_packages(repository_path: str) -> list[str]:
    """
    Dotted package names inferred from directories that contain __init__.py.

    This is structural discovery only; nothing is imported or executed.
    """
    packages: list[str] = []
    for relative in relative_python_paths(repository_path):
        path = Path(relative)
        if path.name != "__init__.py":
            continue
        parts = path.parent.parts
        if not parts:
            continue
        packages.append(".".join(parts))
    return sorted(packages)
