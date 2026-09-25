from pathlib import Path


def find_python_files(repository_path: str) -> list[Path]:
    """
    Find all Python files inside a repository.
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

    python_files = list(repository.rglob("*.py"))

    return sorted(python_files)