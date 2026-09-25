import sys
from pathlib import Path

from app.analysis.engine import analyze_repository, impact_for_name
from app.analysis.impact import ImpactReport, analyze_impact
from app.models.entity import Entity
from app.scanner.repository import find_python_files


def _format_entity(entity: Entity) -> str:
    return (
        f"[{entity.entity_type}] {entity.name} "
        f"({entity.file_path}:{entity.line_number})"
    )


def _print_section(title: str) -> None:
    print(title)
    print("-" * 32)


def _print_entity_list(entities: list[Entity], empty: str) -> None:
    if not entities:
        print(f"  {empty}")
        return
    for entity in entities:
        print(f"  - {_format_entity(entity)}")


def _print_impact(report: ImpactReport) -> None:
    selected = report.selected_entity
    print(f"Selected entity: {_format_entity(selected)}")
    print()
    print("Direct dependencies (this entity uses):")
    _print_entity_list(report.direct_dependencies, "none")
    print()
    print("Indirect dependencies (reachable through others):")
    _print_entity_list(report.indirect_dependencies, "none")
    print()
    print("Direct dependents / callers (potentially affected immediately):")
    _print_entity_list(report.direct_dependents, "none")
    print()
    print("Indirect dependents / callers (potentially affected later):")
    _print_entity_list(report.indirect_dependents, "none")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m app.cli <repository_path>")
        return

    repository_path = sys.argv[1]

    try:
        find_python_files(repository_path)
    except (FileNotFoundError, NotADirectoryError) as error:
        print(f"Error: {error}")
        return

    result = analyze_repository(repository_path)

    print()
    print("================================")
    print("             NEXUS")
    print("       Repository Analyzer")
    print("================================")
    print()
    print(f"Repository: {repository_path}")
    print()

    _print_section("Files discovered")
    print(f"Python files found: {len(result.python_files)}")
    for file_path in result.python_files:
        relative = Path(file_path)
        print(f"  - {relative.as_posix()}")
    print()

    if result.parse_errors:
        _print_section("Parse errors")
        for path, message in result.parse_errors:
            print(f"  - {path}: {message}")
        print()

    _print_section("Entities discovered")
    for entity in result.entities:
        print(f"  {_format_entity(entity)}")
        print(f"    id: {entity.id}")
    print()
    print(f"Total entities: {len(result.entities)}")
    print()

    _print_section("Relationships")
    if not result.relationships:
        print("  none")
    else:
        node = {entity.id: entity for entity in result.entities}
        for rel in result.relationships:
            source = node[rel.source_id]
            target = node[rel.target_id]
            print(
                f"  {source.entity_type}:{source.name} "
                f"--{rel.relationship_type}--> "
                f"{target.entity_type}:{target.name}"
            )
    print()
    print(f"Total relationships: {len(result.relationships)}")
    print()

    _print_section("Graph summary")
    print(f"Nodes: {len(result.graph.nodes())}")
    print(f"Edges: {len(result.graph.edges())}")
    print()

    _print_section("Example impact analysis")
    report = impact_for_name(result, "process_payment", entity_type="function")
    if report is None:
        fallback = next(
            (entity for entity in result.entities if entity.entity_type == "function"),
            None,
        )
        if fallback is None:
            print("  No function entity available for an example report.")
        else:
            print("  process_payment was not found; using the first function instead.")
            print()
            _print_impact(analyze_impact(result.graph, fallback.id))
    else:
        print(
            "This is static analysis. Listed dependents are "
            "potentially affected if the selected entity changes."
        )
        print()
        _print_impact(report)

    print()


if __name__ == "__main__":
    main()
