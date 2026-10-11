from dataclasses import dataclass
from typing import Set

from app.graph.dependency_graph import DependencyGraph
from app.models.entity import Entity
from app.git.models import FileChange, ChangeType
from app.analysis.impact import analyze_impact


@dataclass
class GitImpactReport:
    changes: list[FileChange]
    mapped_entities: list[Entity]
    potentially_affected_dependents: list[Entity]


def analyze_git_impact(
    graph: DependencyGraph, changes: list[FileChange]
) -> GitImpactReport:
    """
    Map Git file changes to graph entities and determine potentially affected dependents.
    """
    mapped_entities: list[Entity] = []

    # Map files to entities
    all_nodes = graph.nodes()
    
    for change in changes:
        if change.change_type == ChangeType.MODIFIED:
            # Map entities whose file_path equals the changed path
            mapped_entities.extend(
                node for node in all_nodes if node.file_path == change.path
            )
        elif change.change_type == ChangeType.DELETED:
            # Map entities from baseline using the old/deleted path
            mapped_entities.extend(
                node for node in all_nodes if node.file_path == change.path
            )
        elif change.change_type == ChangeType.RENAMED:
            # Map baseline entities using old_path
            if change.old_path:
                mapped_entities.extend(
                    node for node in all_nodes if node.file_path == change.old_path
                )
        elif change.change_type == ChangeType.ADDED:
            # No baseline entities; zero baseline impact
            pass

    # Deduplicate mapped entities
    unique_mapped: dict[str, Entity] = {e.id: e for e in mapped_entities}
    deduplicated_mapped = list(unique_mapped.values())

    potentially_affected: dict[str, Entity] = {}

    for entity in deduplicated_mapped:
        # Call the existing analyze_impact() function
        report = analyze_impact(graph, entity.id)
        
        # Union and deduplicate potentially affected dependents
        for dep in report.direct_dependents:
            potentially_affected[dep.id] = dep
        for dep in report.indirect_dependents:
            potentially_affected[dep.id] = dep

    return GitImpactReport(
        changes=changes,
        mapped_entities=deduplicated_mapped,
        potentially_affected_dependents=list(potentially_affected.values()),
    )
