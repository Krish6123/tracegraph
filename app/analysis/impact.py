from dataclasses import dataclass

from app.graph.dependency_graph import DependencyGraph
from app.models.entity import Entity


@dataclass
class ImpactReport:
    selected_entity: Entity
    direct_dependencies: list[Entity]
    indirect_dependencies: list[Entity]
    direct_dependents: list[Entity]
    indirect_dependents: list[Entity]


def _entities_for(graph: DependencyGraph, node_ids: list[str]) -> list[Entity]:
    return [graph.get_node(node_id) for node_id in node_ids]


def analyze_impact(
    graph: DependencyGraph,
    entity_id: str,
    algorithm: str = "bfs",
) -> ImpactReport:
    """
    Report potential impact of changing an entity.

    Traversal uses the dependency graph (not hardcoded call chains).
    Results are "potentially affected" entities: static analysis cannot
    prove that runtime behavior will break.
    """
    if not graph.has_node(entity_id):
        raise KeyError(f"Unknown entity: {entity_id}")

    return ImpactReport(
        selected_entity=graph.get_node(entity_id),
        direct_dependencies=_entities_for(
            graph, graph.direct_dependencies(entity_id)
        ),
        indirect_dependencies=_entities_for(
            graph, graph.indirect_dependencies(entity_id, algorithm=algorithm)
        ),
        direct_dependents=_entities_for(
            graph, graph.direct_dependents(entity_id)
        ),
        indirect_dependents=_entities_for(
            graph, graph.indirect_dependents(entity_id, algorithm=algorithm)
        ),
    )
