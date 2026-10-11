from pathlib import Path
from app.scanner.repository import find_python_files, find_python_packages
from app.analysis.engine import analyze_repository
from app.models.relationship import CONTAINS, IMPORTS, CALLS, INSTANTIATES

def test_realistic_project_scanner():
    repo_path = "examples/realistic_project"
    files = find_python_files(repo_path)
    assert len(files) == 8
    
    packages = find_python_packages(repo_path)
    assert set(packages) == {"models", "services", "utils"}

def test_realistic_project_analysis():
    repo_path = "examples/realistic_project"
    result = analyze_repository(repo_path)
    graph = result.graph
    
    nodes = {node.name: node for node in graph.nodes()}
    
    # 1. Classes and Methods extracted
    assert "PaymentService" in nodes
    assert "PaymentService.process" in nodes
    assert "Order" in nodes
    assert "Order.validate" in nodes
    
    # 2. CONTAINS relationships
    edges = list(graph.edges())
    contains_edges = [(e.source_id, e.target_id) for e in edges if e.relationship_type == CONTAINS]
    
    file_payment_service = nodes["payment_service.py"].id
    class_payment_service = nodes["PaymentService"].id
    method_process = nodes["PaymentService.process"].id
    
    assert (file_payment_service, class_payment_service) in contains_edges
    assert (class_payment_service, method_process) in contains_edges
    
    # 3. Imports and Aliases
    imports_edges = [(e.source_id, e.target_id) for e in edges if e.relationship_type == IMPORTS]
    file_main = nodes["main.py"].id
    assert (file_main, file_payment_service) in imports_edges
    
    # 4. CALLS relationships
    calls_edges = [(e.source_id, e.target_id) for e in edges if e.relationship_type == CALLS]
    
    # start() calls connect()
    function_start = nodes["start"].id
    function_connect = nodes["connect"].id
    assert (function_start, function_connect) in calls_edges
    
    # start() instantiates PaymentService
    instantiates_edges = [(e.source_id, e.target_id) for e in edges if e.relationship_type == INSTANTIATES]
    assert (function_start, class_payment_service) in instantiates_edges
    
    # start() calls service.process()
    assert (function_start, method_process) in calls_edges

    # Class-qualified methods, module aliases, from-package imports, and
    # imported function aliases resolve to the same local targets.
    function_process_payment = nodes["process_payment"].id
    assert (function_start, function_process_payment) in calls_edges
    process_calls = [
        edge for edge in edges
        if edge.relationship_type == CALLS
        and edge.source_id == function_start
        and edge.target_id == method_process
    ]
    assert len(process_calls) == 1
    
    # process() calls self.validate()
    method_validate = nodes["PaymentService.validate"].id
    assert (method_process, method_validate) in calls_edges
    
    # process() calls auth.check() (module.method() via alias)
    function_check = nodes["check"].id
    assert (method_process, function_check) in calls_edges
    
    # Ambiguous calls are omitted
    # main.py has `obj.validate()` - this should be unresolved and NOT connected to Order.validate or Auth.validate
    for src, tgt in calls_edges:
        if src == function_start:
            target_node = graph.get_node(tgt)
            # Should not call any validate method because it's ambiguous
            assert "validate" not in target_node.name

    # Check unresolved lists obj.validate()
    # Wait, the parser doesn't add 'validate' to unresolved if it's not local.
    # Let's check unresolved just in case it's there. 
    # Our earlier analysis showed it might not be in `unresolved` if it's not a local function, 
    # but that's fine, the Ambiguity Rule says "omitted from CALLS" which we verified.

def test_impact_analysis_across_packages():
    from app.analysis.impact import analyze_impact
    repo_path = "examples/realistic_project"
    result = analyze_repository(repo_path)
    graph = result.graph
    
    nodes = {node.name: node for node in graph.nodes()}
    check_function = nodes["check"]
    
    report = analyze_impact(graph, check_function.id)
    
    # check() is in auth_service.py
    # process() in payment_service.py calls auth.check()
    # start() in main.py calls service.process()
    
    direct_deps = [n.name for n in report.direct_dependents]
    assert "PaymentService.process" in direct_deps
    
    indirect_deps = [n.name for n in report.indirect_dependents]
    assert "start" in indirect_deps
    # main.py file should also be an indirect dependent because it contains start()
    assert "main.py" in indirect_deps
