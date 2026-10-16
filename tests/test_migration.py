import sqlite3
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

from app.db.migrations import init_db, run_migrations
from app.db.models import AnalysisRecord
from app.db.repository import get_analysis, get_entities, get_relationships


def test_fresh_database_initialization():
    engine = create_engine("sqlite:///:memory:")

    # Run fresh initialization
    init_db(bind=engine)

    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    assert "analyses" in table_names
    assert "entities" in table_names
    assert "relationships" in table_names
    assert "unresolved_calls" in table_names

    columns = {col["name"] for col in inspector.get_columns("analyses")}
    assert "commit_hash" in columns
    assert "id" in columns
    assert "repository_path" in columns
    assert "status" in columns

    # Verify session operations on fresh database
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    try:
        rec = AnalysisRecord(
            id="test-analysis-fresh",
            repository_path="examples/sample_project",
            status="success",
            commit_hash="a1b2c3d4"
        )
        session.add(rec)
        session.commit()

        fetched = session.query(AnalysisRecord).filter(AnalysisRecord.id == "test-analysis-fresh").first()
        assert fetched is not None
        assert fetched.commit_hash == "a1b2c3d4"
    finally:
        session.close()


def test_migration_from_m4_schema():
    engine = create_engine("sqlite:///:memory:")

    # Create M4 legacy schema directly (without commit_hash)
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE analyses (
                id VARCHAR PRIMARY KEY,
                repository_path VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                parse_errors JSON,
                packages JSON,
                created_at DATETIME
            );
        """))
        conn.execute(text("""
            CREATE TABLE entities (
                id INTEGER PRIMARY KEY,
                analysis_id VARCHAR NOT NULL,
                entity_id VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                entity_type VARCHAR NOT NULL,
                file_path VARCHAR NOT NULL,
                line_number INTEGER NOT NULL,
                parent_id VARCHAR
            );
        """))
        conn.execute(text("""
            CREATE TABLE relationships (
                id INTEGER PRIMARY KEY,
                analysis_id VARCHAR NOT NULL,
                source_id VARCHAR NOT NULL,
                target_id VARCHAR NOT NULL,
                relationship_type VARCHAR NOT NULL
            );
        """))
        conn.execute(text("""
            CREATE TABLE unresolved_calls (
                id INTEGER PRIMARY KEY,
                analysis_id VARCHAR NOT NULL,
                file_path VARCHAR NOT NULL,
                line_number INTEGER NOT NULL,
                expression VARCHAR NOT NULL,
                reason VARCHAR NOT NULL
            );
        """))

        # Seed existing M4 record and relationships
        conn.execute(text("""
            INSERT INTO analyses (id, repository_path, status, parse_errors, packages)
            VALUES ('m4-analysis-1', 'examples/sample_project', 'success', '[]', '[]');
        """))
        conn.execute(text("""
            INSERT INTO entities (id, analysis_id, entity_id, name, entity_type, file_path, line_number)
            VALUES (1, 'm4-analysis-1', 'file:main.py', 'main.py', 'file', 'main.py', 1);
        """))
        conn.execute(text("""
            INSERT INTO relationships (id, analysis_id, source_id, target_id, relationship_type)
            VALUES (1, 'm4-analysis-1', 'file:main.py', 'func:main', 'CONTAINS');
        """))

    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()

    # Pre-migration: verifying that querying with M5 AnalysisRecord fails due to missing commit_hash
    with pytest.raises(OperationalError) as exc_info:
        session.query(AnalysisRecord).filter(AnalysisRecord.id == "m4-analysis-1").first()
    assert "commit_hash" in str(exc_info.value)
    session.rollback()
    session.close()

    # Run migration / init_db
    init_db(bind=engine)

    # Post-migration verification
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("analyses")}
    assert "commit_hash" in columns

    session = TestingSession()
    try:
        # Existing record is preserved and accessible via ORM
        analysis = get_analysis(session, "m4-analysis-1")
        assert analysis is not None
        assert analysis.id == "m4-analysis-1"
        assert analysis.repository_path == "examples/sample_project"
        assert analysis.commit_hash is None

        # Existing entities and relationships are preserved
        entities = get_entities(session, "m4-analysis-1")
        assert len(entities) == 1
        assert entities[0].name == "main.py"

        relationships = get_relationships(session, "m4-analysis-1")
        assert len(relationships) == 1
        assert relationships[0].relationship_type == "CONTAINS"

        # New M5 record with commit_hash can be added alongside M4 record
        rec2 = AnalysisRecord(
            id="m5-analysis-2",
            repository_path="examples/sample_project",
            status="success",
            commit_hash="c0ffee123"
        )
        session.add(rec2)
        session.commit()

        fetched2 = get_analysis(session, "m5-analysis-2")
        assert fetched2 is not None
        assert fetched2.commit_hash == "c0ffee123"
    finally:
        session.close()


def test_migration_is_idempotent():
    engine = create_engine("sqlite:///:memory:")

    # Initial run
    init_db(bind=engine)
    inspector1 = inspect(engine)
    cols1 = {col["name"] for col in inspector1.get_columns("analyses")}
    assert "commit_hash" in cols1

    # Second run of run_migrations
    run_migrations(bind=engine)
    inspector2 = inspect(engine)
    cols2 = {col["name"] for col in inspector2.get_columns("analyses")}
    assert cols2 == cols1

    # Third run of init_db
    init_db(bind=engine)
    inspector3 = inspect(engine)
    cols3 = {col["name"] for col in inspector3.get_columns("analyses")}
    assert cols3 == cols1
