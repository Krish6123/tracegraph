import pytest
from fastapi.testclient import TestClient
import subprocess
from app.main import app
from app.db.database import Base, engine, SessionLocal
from app.api.deps import get_db

client = TestClient(app)

@pytest.fixture(scope="module")
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session(setup_db):
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_git_impact_api(tmp_path):
    # 1. Initialize git repo
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    
    subprocess.run(["git", "init"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
    
    # Create baseline file
    file1 = repo_dir / "file1.py"
    file1.write_text("def my_func(): pass\n")
    
    file2 = repo_dir / "file2.py"
    file2.write_text("from file1 import my_func\nmy_func()\n")
    
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True)
    
    # 2. Run analysis
    res = client.post("/analyze", json={"repository_path": str(repo_dir)})
    assert res.status_code == 200
    analysis_id = res.json()["analysis_id"]
    
    # 3. Modify file1.py
    file1.write_text("def my_func():\n    return True\n")
    
    # 4. Request git-impact (working tree)
    res = client.post(f"/analysis/{analysis_id}/git-impact", json={})
    assert res.status_code == 200
    
    data = res.json()
    assert len(data["changes"]) == 1
    assert data["changes"][0]["path"] == "file1.py"
    assert data["changes"][0]["change_type"] == "modified"
    
    mapped = {e["file_path"] for e in data["mapped_entities"]}
    assert "file1.py" in mapped
    
    affected = {e["file_path"] for e in data["potentially_affected_dependents"]}
    assert "file2.py" in affected
