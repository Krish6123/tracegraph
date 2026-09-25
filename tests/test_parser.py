from pathlib import Path

from app.parser.ast_parser import (
    extract_entities,
    parse_python_file,
)


def test_extract_function():
    file_path = Path("examples/sample_project/payment.py")

    tree = parse_python_file(file_path)

    entities = extract_entities(
        tree,
        file_path,
    )

    assert len(entities) == 1
    assert entities[0].name == "process_payment"
    assert entities[0].entity_type == "function"