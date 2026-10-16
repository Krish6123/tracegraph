from sqlalchemy import inspect, text
from app.db.database import Base, engine


def run_migrations(bind=None) -> None:
    """
    Run lightweight, safe schema migrations for existing databases.
    Preserves all existing data and relationships without recreating tables.
    """
    target = bind if bind is not None else engine
    inspector = inspect(target)
    tables = inspector.get_table_names()

    # Milestone 5 migration: add commit_hash column to analyses table if missing
    if "analyses" in tables:
        columns = [col["name"] for col in inspector.get_columns("analyses")]
        if "commit_hash" not in columns:
            if hasattr(target, "begin"):
                with target.begin() as conn:
                    conn.execute(text("ALTER TABLE analyses ADD COLUMN commit_hash VARCHAR"))
            else:
                target.execute(text("ALTER TABLE analyses ADD COLUMN commit_hash VARCHAR"))


def init_db(bind=None) -> None:
    """
    Initialize database tables and apply incremental schema migrations.
    Works for both fresh databases and existing databases from previous milestones.
    """
    target = bind if bind is not None else engine
    Base.metadata.create_all(bind=target)
    run_migrations(bind=target)
