from app.scanner.repository import find_python_files


def test_find_python_files():
    files = find_python_files("examples/sample_project")

    assert len(files) == 4
    assert all(file.suffix == ".py" for file in files)