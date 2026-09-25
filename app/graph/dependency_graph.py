from collections import deque

from app.models.entity import Entity
from app.models.relationship import Relationship


class DependencyGraph:
    """
    Directed adjacency-list graph of code entities.

    Forward edges follow relationships as extracted (e.g. CALLS, IMPORTS,
    CONTAINS). Reverse edges answer "who points at this node?".
    """

    def __init__(self) -> None:
        self._nodes: dict[str, Entity] = {}
        self._forward: dict[str, list[tuple[str, str]]] = {}
        self._reverse: dict[str, list[tuple[str, str]]] = {}
        self._edges: list[Relationship] = []
        self._edge_keys: set[tuple[str, str, str]] = set()

    def add_node(self, entity: Entity) -> None:
        if entity.id in self._nodes:
            return
        self._nodes[entity.id] = entity
        self._forward.setdefault(entity.id, [])
        self._reverse.setdefault(entity.id, [])

    def add_edge(self, relationship: Relationship) -> None:
        if relationship.source_id not in self._nodes:
            raise KeyError(f"Unknown source node: {relationship.source_id}")
        if relationship.target_id not in self._nodes:
            raise KeyError(f"Unknown target node: {relationship.target_id}")

        key = (
            relationship.source_id,
            relationship.target_id,
            relationship.relationship_type,
        )
        if key in self._edge_keys:
            return

        self._edge_keys.add(key)
        self._edges.append(relationship)
        self._forward[relationship.source_id].append(
            (relationship.target_id, relationship.relationship_type)
        )
        self._reverse[relationship.target_id].append(
            (relationship.source_id, relationship.relationship_type)
        )

    def get_node(self, node_id: str) -> Entity:
        return self._nodes[node_id]

    def nodes(self) -> list[Entity]:
        return list(self._nodes.values())

    def edges(self) -> list[Relationship]:
        return list(self._edges)

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def forward_neighbors(self, node_id: str) -> list[str]:
        """Immediate outgoing node IDs (duplicates removed, order preserved)."""
        return self._unique([target for target, _rel in self._forward.get(node_id, [])])

    def reverse_neighbors(self, node_id: str) -> list[str]:
        """Immediate incoming node IDs (duplicates removed, order preserved)."""
        return self._unique([source for source, _rel in self._reverse.get(node_id, [])])

    def forward_graph(self) -> dict[str, list[str]]:
        return {node_id: self.forward_neighbors(node_id) for node_id in self._nodes}

    def reverse_graph(self) -> dict[str, list[str]]:
        return {node_id: self.reverse_neighbors(node_id) for node_id in self._nodes}

    def traverse(
        self,
        start_id: str,
        direction: str = "forward",
        algorithm: str = "dfs",
        include_start: bool = False,
    ) -> list[str]:
        """
        Walk the graph with a visited set so cycles cannot loop forever.

        direction: "forward" (dependencies) or "reverse" (dependents)
        algorithm: "dfs" or "bfs"
        """
        if start_id not in self._nodes:
            raise KeyError(f"Unknown node: {start_id}")

        adjacency = (
            self.forward_neighbors if direction == "forward" else self.reverse_neighbors
        )

        if algorithm == "bfs":
            order = self._bfs(start_id, adjacency)
        elif algorithm == "dfs":
            order = self._dfs(start_id, adjacency)
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")

        if include_start:
            return order
        return [node_id for node_id in order if node_id != start_id]

    def direct_dependencies(self, node_id: str) -> list[str]:
        return self.forward_neighbors(node_id)

    def direct_dependents(self, node_id: str) -> list[str]:
        return self.reverse_neighbors(node_id)

    def indirect_dependencies(self, node_id: str, algorithm: str = "bfs") -> list[str]:
        reachable = self.traverse(node_id, direction="forward", algorithm=algorithm)
        direct = set(self.direct_dependencies(node_id))
        return [node_id_ for node_id_ in reachable if node_id_ not in direct]

    def indirect_dependents(self, node_id: str, algorithm: str = "bfs") -> list[str]:
        reachable = self.traverse(node_id, direction="reverse", algorithm=algorithm)
        direct = set(self.direct_dependents(node_id))
        return [node_id_ for node_id_ in reachable if node_id_ not in direct]

    def _dfs(self, start_id: str, adjacency) -> list[str]:
        visited: set[str] = set()
        order: list[str] = []

        def visit(node_id: str) -> None:
            if node_id in visited:
                return
            visited.add(node_id)
            order.append(node_id)
            for neighbor in adjacency(node_id):
                visit(neighbor)

        visit(start_id)
        return order

    def _bfs(self, start_id: str, adjacency) -> list[str]:
        visited = {start_id}
        order = [start_id]
        queue = deque([start_id])

        while queue:
            node_id = queue.popleft()
            for neighbor in adjacency(node_id):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                order.append(neighbor)
                queue.append(neighbor)

        return order

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            unique.append(value)
        return unique
