import subprocess
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import Base
from app.db.migrations import init_db
from app.db.models import AnalysisRecord
from app.api.deps import get_db

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
init_db(bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


def _init_git_repo(repo_dir):
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True, capture_output=True)


def test_git_impact_api(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _init_git_repo(repo_dir)

    file1 = repo_dir / "file1.py"
    file1.write_text("def my_func(): pass\n")

    file2 = repo_dir / "file2.py"
    file2.write_text("from file1 import my_func\nmy_func()\n")

    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True)

    # Run analysis
    res = client.post("/analyze", json={"repository_path": str(repo_dir)})
    assert res.status_code == 200
    analysis_id = res.json()["analysis_id"]

    # Modify file1.py
    file1.write_text("def my_func():\n    return True\n")

    # Request git-impact (working tree default)
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


def test_git_impact_saved_analysis_commit_label(tmp_path):
    repo_dir = tmp_path / "repo_label"
    repo_dir.mkdir()
    _init_git_repo(repo_dir)

    file1 = repo_dir / "file1.py"
    file1.write_text("def my_func(): pass\n")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True)

    res = client.post("/analyze", json={"repository_path": str(repo_dir)})
    assert res.status_code == 200
    analysis_id = res.json()["analysis_id"]

    file1.write_text("def my_func(): return 42\n")

    # The UI label "Saved analysis commit" should resolve to the saved commit_hash
    res = client.post(f"/analysis/{analysis_id}/git-impact", json={"base_ref": "Saved analysis commit"})
    assert res.status_code == 200
    data = res.json()
    assert len(data["changes"]) == 1
    assert data["changes"][0]["path"] == "file1.py"


def test_git_impact_explicit_git_references(tmp_path):
    repo_dir = tmp_path / "repo_explicit"
    repo_dir.mkdir()
    _init_git_repo(repo_dir)

    file1 = repo_dir / "file1.py"
    file1.write_text("def my_func(): pass\n")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True)

    res = client.post("/analyze", json={"repository_path": str(repo_dir)})
    assert res.status_code == 200
    analysis_id = res.json()["analysis_id"]

    file1.write_text("def my_func(): return 'changed'\n")

    # 1. Valid explicit base_ref "HEAD"
    res = client.post(f"/analysis/{analysis_id}/git-impact", json={"base_ref": "HEAD"})
    assert res.status_code == 200
    assert len(res.json()["changes"]) == 1

    # 2. Non-existent explicit base_ref
    res = client.post(f"/analysis/{analysis_id}/git-impact", json={"base_ref": "non_existent_branch_xyz"})
    assert res.status_code == 400
    assert "Git reference 'non_existent_branch_xyz' does not exist in repository" in res.json()["detail"]

    # 3. Non-existent explicit target_ref
    res = client.post(f"/analysis/{analysis_id}/git-impact", json={"base_ref": "HEAD", "target_ref": "invalid_target_ref"})
    assert res.status_code == 400
    assert "Git target reference 'invalid_target_ref' does not exist in repository" in res.json()["detail"]


def test_git_impact_missing_saved_commit_hash(tmp_path):
    repo_dir = tmp_path / "repo_no_commit"
    repo_dir.mkdir()
    _init_git_repo(repo_dir)

    file1 = repo_dir / "file1.py"
    file1.write_text("def my_func(): pass\n")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True)

    res = client.post("/analyze", json={"repository_path": str(repo_dir)})
    assert res.status_code == 200
    analysis_id = res.json()["analysis_id"]

    # Clear commit_hash to simulate legacy or unversioned analysis
    db = TestingSessionLocal()
    record = db.query(AnalysisRecord).filter(AnalysisRecord.id == analysis_id).first()
    record.commit_hash = None
    db.commit()
    db.close()

    # Omitted base_ref should return clear actionable 400
    res = client.post(f"/analysis/{analysis_id}/git-impact", json={})
    assert res.status_code == 400
    assert "Analysis has no saved commit hash. Please specify a valid base Git reference." in res.json()["detail"]

    # "Saved analysis commit" label should also return the actionable 400
    res = client.post(f"/analysis/{analysis_id}/git-impact", json={"base_ref": "Saved analysis commit"})
    assert res.status_code == 400
    assert "Analysis has no saved commit hash. Please specify a valid base Git reference." in res.json()["detail"]

    # User providing an explicit valid reference succeeds
    res = client.post(f"/analysis/{analysis_id}/git-impact", json={"base_ref": "HEAD"})
    assert res.status_code == 200


def test_git_impact_non_git_repository(tmp_path):
    non_git_dir = tmp_path / "non_git"
    non_git_dir.mkdir()
    file1 = non_git_dir / "file1.py"
    file1.write_text("def foo(): pass\n")

    res = client.post("/analyze", json={"repository_path": str(non_git_dir)})
    assert res.status_code == 200
    analysis_id = res.json()["analysis_id"]

    res = client.post(f"/analysis/{analysis_id}/git-impact", json={})
    assert res.status_code == 400
    assert "Repository path is not a Git repository" in res.json()["detail"]
