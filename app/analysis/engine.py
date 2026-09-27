from dataclasses import dataclass, field
from pathlib import Path

from app.analysis.impact import ImpactReport, analyze_impact
from app.graph.dependency_graph import DependencyGraph
from app.models.entity import Entity
from app.models.relationship import Relationship
from app.parser.ast_parser import (
    UnresolvedCall,
    extract_repository_entities_and_relationships,
    parse_python_file,
)
from app.scanner.repository import find_python_files, find_python_packages


@dataclass
class AnalysisResult:
    repository_path: str
    python_files: list[Path]
    entities: list[Entity]
    relationships: list[Relationship]
    graph: DependencyGraph
    parse_errors: list[tuple[str, str]] = field(default_factory=list)
    packages: list[str] = field(default_factory=list)
    unresolved_calls: list[UnresolvedCall] = field(default_factory=list)

    def entity_by_name(self, name: str, entity_type: str | None = None) -> Entity | None:
        for entity in self.entities:
            if entity.name != name:
                continue
            if entity_type is not None and entity.entity_type != entity_type:
                continue
            return entity
        return None


def _relative_path(file_path: Path, repository_root: Path) -> str:
    try:
        return file_path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError:
        return file_path.as_posix()


def analyze_repository(repository_path: str) -> AnalysisResult:
    """
    Scan a repository, extract entities/relationships, and build the graph.
    """
    python_files = find_python_files(repository_path)
    repository_root = Path(repository_path)
    packages = find_python_packages(repository_path)

    parsed_files: list[tuple[str, object]] = []
    parse_errors: list[tuple[str, str]] = []

    for file_path in python_files:
        relative = _relative_path(Path(file_path), repository_root)
        try:
            tree = parse_python_file(Path(file_path))
        except SyntaxError as error:
            parse_errors.append((relative, str(error)))
            continue
        parsed_files.append((relative, tree))

    entities, relationships, unresolved_calls = (
        extract_repository_entities_and_relationships(parsed_files)
    )

    graph = DependencyGraph()
    for entity in entities:
        graph.add_node(entity)
    for relationship in relationships:
        graph.add_edge(relationship)

    return AnalysisResult(
        repository_path=str(repository_path),
        python_files=python_files,
        entities=entities,
        relationships=relationships,
        graph=graph,
        parse_errors=parse_errors,
        packages=packages,
        unresolved_calls=unresolved_calls,
    )


def impact_for_name(
    result: AnalysisResult,
    name: str,
    entity_type: str | None = None,
) -> ImpactReport | None:
    entity = result.entity_by_name(name, entity_type=entity_type)
    if entity is None:
        return None
    return analyze_impact(result.graph, entity.id)
