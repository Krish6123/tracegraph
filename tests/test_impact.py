from app.analysis.engine import analyze_repository
from app.analysis.impact import analyze_impact


def test_impact_analysis_on_sample_process_payment():
    result = analyze_repository("examples/sample_project")
    process_payment = result.entity_by_name("process_payment", entity_type="function")
    assert process_payment is not None

    report = analyze_impact(result.graph, process_payment.id)

    assert report.selected_entity.name == "process_payment"

    direct_dep_names = {entity.name for entity in report.direct_dependencies}
    indirect_dep_names = {entity.name for entity in report.indirect_dependencies}
    direct_dependent_names = {entity.name for entity in report.direct_dependents}
    indirect_dependent_names = {entity.name for entity in report.indirect_dependents}

    assert "save_transaction" in direct_dep_names
    assert "save_transaction" not in indirect_dep_names
    assert "create_order" in direct_dependent_names
    assert "main" in indirect_dependent_names
    assert "main" not in direct_dependent_names


def test_impact_uses_graph_traversal_not_hardcoded_names(tmp_path):
    (tmp_path / "alpha.py").write_text(
        "def alpha():\n    return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "beta.py").write_text(
        "from alpha import alpha\n"
        "\n"
        "def beta():\n"
        "    alpha()\n",
        encoding="utf-8",
    )
    (tmp_path / "gamma.py").write_text(
        "from beta import beta\n"
        "\n"
        "def gamma():\n"
        "    beta()\n",
        encoding="utf-8",
    )

    result = analyze_repository(str(tmp_path))
    alpha = result.entity_by_name("alpha", entity_type="function")
    report = analyze_impact(result.graph, alpha.id)

    assert {entity.name for entity in report.direct_dependents} >= {"beta"}
    assert {entity.name for entity in report.indirect_dependents} >= {"gamma"}


def test_cyclic_repository_impact_terminates(tmp_path):
    (tmp_path / "left.py").write_text(
        "from right import go_right\n"
        "\n"
        "def go_left():\n"
        "    go_right()\n",
        encoding="utf-8",
    )
    (tmp_path / "right.py").write_text(
        "from left import go_left\n"
        "\n"
        "def go_right():\n"
        "    go_left()\n",
        encoding="utf-8",
    )

    result = analyze_repository(str(tmp_path))
    go_left = result.entity_by_name("go_left", entity_type="function")
    report = analyze_impact(result.graph, go_left.id)

    names = {
        entity.name
        for entity in (
            report.direct_dependencies
            + report.indirect_dependencies
            + report.direct_dependents
            + report.indirect_dependents
        )
    }
    assert "go_right" in names
    assert report.selected_entity.name == "go_left"
