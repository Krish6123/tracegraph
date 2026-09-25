from pathlib import Path

from app.analysis.engine import analyze_repository
from app.models.relationship import CALLS, CONTAINS, IMPORTS
from app.parser.ast_parser import (
    extract_entities,
    extract_relationships,
    parse_python_file,
)


def _rel_types(result, source_name, target_name):
    entities = {entity.id: entity for entity in result.entities}
    types = []
    for rel in result.relationships:
        source = entities[rel.source_id]
        target = entities[rel.target_id]
        if source.name == source_name and target.name == target_name:
            types.append(rel.relationship_type)
    return types


def test_contains_file_to_function():
    result = analyze_repository("examples/sample_project")
    assert CONTAINS in _rel_types(result, "payment.py", "process_payment")
    assert CONTAINS in _rel_types(result, "orders.py", "create_order")
    assert CONTAINS in _rel_types(result, "database.py", "save_transaction")
    assert CONTAINS in _rel_types(result, "main.py", "main")


def test_imports_from_module_import():
    result = analyze_repository("examples/sample_project")
    assert IMPORTS in _rel_types(result, "orders.py", "payment.py")
    assert IMPORTS in _rel_types(result, "main.py", "orders.py")
    assert IMPORTS in _rel_types(result, "payment.py", "database.py")


def test_calls_from_imported_name():
    result = analyze_repository("examples/sample_project")
    assert CALLS in _rel_types(result, "create_order", "process_payment")
    assert CALLS in _rel_types(result, "process_payment", "save_transaction")
    assert CALLS in _rel_types(result, "main", "create_order")


def test_import_module_attribute_call(tmp_path):
    (tmp_path / "payment.py").write_text(
        "def process_payment():\n    return True\n",
        encoding="utf-8",
    )
    (tmp_path / "checkout.py").write_text(
        "import payment\n"
        "\n"
        "def checkout():\n"
        "    payment.process_payment()\n",
        encoding="utf-8",
    )

    result = analyze_repository(str(tmp_path))
    assert IMPORTS in _rel_types(result, "checkout.py", "payment.py")
    assert CALLS in _rel_types(result, "checkout", "process_payment")


def test_unresolved_third_party_import_is_skipped(tmp_path):
    (tmp_path / "app.py").write_text(
        "import json\n"
        "\n"
        "def load():\n"
        "    return json.loads('{}')\n",
        encoding="utf-8",
    )

    result = analyze_repository(str(tmp_path))
    import_rels = [
        rel for rel in result.relationships if rel.relationship_type == IMPORTS
    ]
    call_rels = [
        rel for rel in result.relationships if rel.relationship_type == CALLS
    ]
    assert import_rels == []
    assert call_rels == []


def test_extract_relationships_single_file_local_call():
    file_path = Path("examples/sample_project/database.py")
    tree = parse_python_file(file_path)
    entities = extract_entities(tree, file_path)
    relationships = extract_relationships(tree, entities, file_path=file_path)

    types = {rel.relationship_type for rel in relationships}
    assert CONTAINS in types
    assert CALLS not in types
