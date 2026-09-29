from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


from app.main import app
from app.db.database import Base
from app.api.deps import get_db

# Use in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_analyze_sample_project():
    response = client.post("/analyze", json={"repository_path": "examples/sample_project"})
    assert response.status_code == 200
    data = response.json()
    assert "analysis_id" in data
    assert data["total_entities"] == 8
    assert data["total_relationships"] == 10
    
    analysis_id = data["analysis_id"]
    
    # Test GET summary
    summary_response = client.get(f"/analysis/{analysis_id}")
    assert summary_response.status_code == 200
    assert summary_response.json()["total_entities"] == 8
    
    # Test GET entities
    entities_response = client.get(f"/analysis/{analysis_id}/entities")
    assert entities_response.status_code == 200
    entities = entities_response.json()
    assert len(entities) == 8
    assert any(e["name"] == "process_payment" for e in entities)
    
    # Test GET relationships
    relationships_response = client.get(f"/analysis/{analysis_id}/relationships")
    assert relationships_response.status_code == 200
    assert len(relationships_response.json()) == 10
    
    # Test GET impact
    process_payment = next(e for e in entities if e["name"] == "process_payment")
    impact_response = client.get(f"/analysis/{analysis_id}/impact?entity_id={process_payment['id']}")
    assert impact_response.status_code == 200
    impact = impact_response.json()
    assert impact["selected_entity"]["name"] == "process_payment"
    assert len(impact["direct_dependencies"]) == 1

def test_invalid_analysis_id():
    response = client.get("/analysis/invalid-id")
    assert response.status_code == 404

def test_invalid_repository_path():
    response = client.post("/analyze", json={"repository_path": "invalid_path/that_does_not_exist"})
    assert response.status_code == 400

def test_non_directory_path():
    response = client.post("/analyze", json={"repository_path": "examples/sample_project/main.py"})
    assert response.status_code == 400

def test_unknown_entity_id():
    response = client.post("/analyze", json={"repository_path": "examples/sample_project"})
    analysis_id = response.json()["analysis_id"]
    
    impact_response = client.get(f"/analysis/{analysis_id}/impact?entity_id=invalid-entity-id")
    assert impact_response.status_code == 404

def test_invalid_request_body():
    response = client.post("/analyze", json={"wrong_key": "examples/sample_project"})
    assert response.status_code == 422
