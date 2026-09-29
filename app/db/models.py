import uuid
import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint, JSON
from app.db.database import Base

class AnalysisRecord(Base):
    __tablename__ = "analyses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_path = Column(String, nullable=False)
    status = Column(String, nullable=False)
    parse_errors = Column(JSON, nullable=True)
    packages = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class EntityRecord(Base):
    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(String, ForeignKey("analyses.id"), nullable=False, index=True)
    entity_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    line_number = Column(Integer, nullable=False)
    parent_id = Column(String, nullable=True)
    
    __table_args__ = (
        UniqueConstraint('analysis_id', 'entity_id', name='uq_analysis_entity'),
    )

class RelationshipRecord(Base):
    __tablename__ = "relationships"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(String, ForeignKey("analyses.id"), nullable=False, index=True)
    source_id = Column(String, nullable=False)
    target_id = Column(String, nullable=False)
    relationship_type = Column(String, nullable=False)

class UnresolvedCallRecord(Base):
    __tablename__ = "unresolved_calls"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(String, ForeignKey("analyses.id"), nullable=False, index=True)
    file_path = Column(String, nullable=False)
    line_number = Column(Integer, nullable=False)
    expression = Column(String, nullable=False)
    reason = Column(String, nullable=False)
