import pytest
from app.graph.dependency_graph import DependencyGraph
from app.models.entity import Entity, make_entity_id, FILE, FUNCTION
from app.models.relationship import Relationship
from app.git.models import FileChange, ChangeType
from app.analysis.git_impact import analyze_git_impact

def test_analyze_git_impact():
    graph = DependencyGraph()
    
    # file1.py has a function
    f1_id = make_entity_id(FILE, "file1.py")
    graph.add_node(Entity(id=f1_id, name="file1.py", entity_type=FILE, file_path="file1.py", line_number=1))
    
    func1_id = make_entity_id(FUNCTION, "file1.py", "func1", 2)
    graph.add_node(Entity(id=func1_id, name="func1", entity_type=FUNCTION, file_path="file1.py", line_number=2, parent_id=f1_id))
    
    # file2.py depends on func1
    f2_id = make_entity_id(FILE, "file2.py")
    graph.add_node(Entity(id=f2_id, name="file2.py", entity_type=FILE, file_path="file2.py", line_number=1))
    
    func2_id = make_entity_id(FUNCTION, "file2.py", "func2", 2)
    graph.add_node(Entity(id=func2_id, name="func2", entity_type=FUNCTION, file_path="file2.py", line_number=2, parent_id=f2_id))
    
    graph.add_edge(Relationship(source_id=func2_id, target_id=func1_id, relationship_type="CALLS"))
    
    # file3.py depends on func2
    f3_id = make_entity_id(FILE, "file3.py")
    graph.add_node(Entity(id=f3_id, name="file3.py", entity_type=FILE, file_path="file3.py", line_number=1))
    
    func3_id = make_entity_id(FUNCTION, "file3.py", "func3", 2)
    graph.add_node(Entity(id=func3_id, name="func3", entity_type=FUNCTION, file_path="file3.py", line_number=2, parent_id=f3_id))
    
    graph.add_edge(Relationship(source_id=func3_id, target_id=func2_id, relationship_type="CALLS"))
    
    changes = [
        FileChange(ChangeType.MODIFIED, "file1.py"),
        FileChange(ChangeType.ADDED, "new_file.py"),
        FileChange(ChangeType.DELETED, "file4_missing.py"),
    ]
    
    report = analyze_git_impact(graph, changes)
    
    assert len(report.changes) == 3
    
    mapped_ids = {e.id for e in report.mapped_entities}
    assert mapped_ids == {f1_id, func1_id}
    
    affected_ids = {e.id for e in report.potentially_affected_dependents}
    # func1 dependents are func2 (direct) and func3 (indirect)
    assert func2_id in affected_ids
    assert func3_id in affected_ids

def test_rename_impact():
    graph = DependencyGraph()
    old_id = make_entity_id(FILE, "old.py")
    graph.add_node(Entity(id=old_id, name="old.py", entity_type=FILE, file_path="old.py", line_number=1))
    
    dep_id = make_entity_id(FILE, "dep.py")
    graph.add_node(Entity(id=dep_id, name="dep.py", entity_type=FILE, file_path="dep.py", line_number=1))
    graph.add_edge(Relationship(source_id=dep_id, target_id=old_id, relationship_type="IMPORTS"))
    
    changes = [
        FileChange(ChangeType.RENAMED, "new.py", old_path="old.py")
    ]
    
    report = analyze_git_impact(graph, changes)
    assert len(report.mapped_entities) == 1
    assert report.mapped_entities[0].id == old_id
    
    affected = {e.id for e in report.potentially_affected_dependents}
    assert dep_id in affected
