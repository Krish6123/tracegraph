from app.graph.dependency_graph import DependencyGraph
from app.models.entity import Entity
from app.models.relationship import CALLS, Relationship


def _entity(node_id: str, name: str) -> Entity:
    return Entity(
        id=node_id,
        name=name,
        entity_type="function",
        file_path=f"{name}.py",
        line_number=1,
    )


def _edge(source: str, target: str) -> Relationship:
    return Relationship(
        source_id=source,
        target_id=target,
        relationship_type=CALLS,
    )


def _sample_graph() -> DependencyGraph:
    graph = DependencyGraph()
    for name in ("a", "b", "c"):
        graph.add_node(_entity(name, name))
    graph.add_edge(_edge("a", "b"))
    graph.add_edge(_edge("b", "c"))
    return graph


def test_add_node_and_edge():
    graph = _sample_graph()
    assert len(graph.nodes()) == 3
    assert len(graph.edges()) == 2
    assert graph.get_node("a").name == "a"


def test_duplicate_node_and_edge_are_ignored():
    graph = _sample_graph()
    graph.add_node(_entity("a", "a"))
    graph.add_edge(_edge("a", "b"))
    assert len(graph.nodes()) == 3
    assert len(graph.edges()) == 2


def test_forward_and_reverse_neighbors():
    graph = _sample_graph()
    assert graph.forward_neighbors("a") == ["b"]
    assert graph.forward_neighbors("b") == ["c"]
    assert graph.reverse_neighbors("c") == ["b"]
    assert graph.reverse_neighbors("b") == ["a"]
    assert graph.reverse_neighbors("a") == []


def test_forward_and_reverse_graph():
    graph = _sample_graph()
    assert graph.forward_graph()["a"] == ["b"]
    assert graph.forward_graph()["c"] == []
    assert graph.reverse_graph()["c"] == ["b"]
    assert graph.reverse_graph()["a"] == []


def test_dfs_and_bfs_order():
    graph = DependencyGraph()
    for name in ("a", "b", "c", "d"):
        graph.add_node(_entity(name, name))
    graph.add_edge(_edge("a", "b"))
    graph.add_edge(_edge("a", "c"))
    graph.add_edge(_edge("b", "d"))
    graph.add_edge(_edge("c", "d"))

    dfs = graph.traverse("a", direction="forward", algorithm="dfs")
    bfs = graph.traverse("a", direction="forward", algorithm="bfs")

    assert dfs[0] == "b"
    assert set(dfs) == {"b", "c", "d"}
    assert bfs == ["b", "c", "d"]


def test_direct_vs_indirect_dependencies():
    graph = _sample_graph()
    assert graph.direct_dependencies("a") == ["b"]
    assert graph.indirect_dependencies("a") == ["c"]
    assert graph.direct_dependents("c") == ["b"]
    assert graph.indirect_dependents("c") == ["a"]


def test_cyclic_dependencies_do_not_loop_forever():
    graph = DependencyGraph()
    graph.add_node(_entity("a", "a"))
    graph.add_node(_entity("b", "b"))
    graph.add_edge(_edge("a", "b"))
    graph.add_edge(_edge("b", "a"))

    forward = graph.traverse("a", direction="forward", algorithm="dfs")
    reverse = graph.traverse("a", direction="reverse", algorithm="bfs")

    assert forward == ["b"]
    assert reverse == ["b"]
    assert "a" not in forward
