from pathlib import Path

from app.models.entity import CLASS, FILE, FUNCTION
from app.parser.ast_parser import extract_entities, parse_python_file


def test_extract_function():
    file_path = Path("examples/sample_project/payment.py")

    tree = parse_python_file(file_path)
    entities = extract_entities(tree, file_path)

    functions = [entity for entity in entities if entity.entity_type == FUNCTION]
    assert len(functions) == 1
    assert functions[0].name == "process_payment"
    assert functions[0].entity_type == "function"
    assert functions[0].line_number == 3
    assert functions[0].file_path.endswith("payment.py")


def test_extract_file_entity():
    file_path = Path("examples/sample_project/payment.py")
    tree = parse_python_file(file_path)
    entities = extract_entities(tree, file_path)

    files = [entity for entity in entities if entity.entity_type == FILE]
    assert len(files) == 1
    assert files[0].name == "payment.py"
    assert files[0].line_number == 1
    assert files[0].id == f"file:{file_path.as_posix()}"


def test_entity_ids_are_stable_and_unique():
    file_path = Path("examples/sample_project/orders.py")
    tree = parse_python_file(file_path)

    first = extract_entities(tree, file_path)
    second = extract_entities(tree, file_path)

    first_ids = [entity.id for entity in first]
    second_ids = [entity.id for entity in second]

    assert first_ids == second_ids
    assert len(first_ids) == len(set(first_ids))


def test_extract_class_and_method(tmp_path):
    file_path = tmp_path / "catalog.py"
    file_path.write_text(
        "class Catalog:\n"
        "    def items(self):\n"
        "        return []\n",
        encoding="utf-8",
    )

    tree = parse_python_file(file_path)
    entities = extract_entities(tree, file_path)

    types = {entity.entity_type for entity in entities}
    assert FILE in types
    assert CLASS in types
    assert FUNCTION in types

    catalog = next(entity for entity in entities if entity.name == "Catalog")
    items = next(entity for entity in entities if entity.name == "items")
    assert catalog.entity_type == CLASS
    assert items.entity_type == FUNCTION
    assert catalog.line_number == 1
    assert items.line_number == 2
