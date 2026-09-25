from pathlib import Path

import pytest

from app.scanner.repository import find_python_files


def test_find_python_files():
    files = find_python_files("examples/sample_project")

    assert len(files) == 4
    assert all(file.suffix == ".py" for file in files)


def test_invalid_repository_path():
    with pytest.raises(FileNotFoundError):
        find_python_files("examples/this_repository_does_not_exist")


def test_path_is_not_a_directory(tmp_path):
    file_path = tmp_path / "not_a_repo.py"
    file_path.write_text("x = 1\n", encoding="utf-8")

    with pytest.raises(NotADirectoryError):
        find_python_files(str(file_path))


def test_scanner_returns_sorted_paths():
    files = find_python_files("examples/sample_project")
    names = [Path(path).name for path in files]
    assert names == sorted(names)
