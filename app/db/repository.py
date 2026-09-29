from sqlalchemy.orm import Session
from app.db.models import AnalysisRecord, EntityRecord, RelationshipRecord, UnresolvedCallRecord
from app.analysis.engine import AnalysisResult
from app.models.entity import Entity
from app.models.relationship import Relationship
from app.models.unresolved import UnresolvedCall
from app.graph.dependency_graph import DependencyGraph

def save_analysis(session: Session, analysis_id: str, result: AnalysisResult) -> None:
    analysis_record = AnalysisRecord(
        id=analysis_id,
        repository_path=result.repository_path,
        status="success",
        parse_errors=result.parse_errors,
        packages=result.packages
    )
    session.add(analysis_record)

    entity_records = [
        EntityRecord(
            analysis_id=analysis_id,
            entity_id=e.id,
            name=e.name,
            entity_type=e.entity_type,
            file_path=e.file_path,
            line_number=e.line_number,
            parent_id=e.parent_id
        ) for e in result.entities
    ]
    session.add_all(entity_records)

    relationship_records = [
        RelationshipRecord(
            analysis_id=analysis_id,
            source_id=r.source_id,
            target_id=r.target_id,
            relationship_type=r.relationship_type
        ) for r in result.relationships
    ]
    session.add_all(relationship_records)
    
    unresolved_records = [
        UnresolvedCallRecord(
            analysis_id=analysis_id,
            file_path=u.file_path,
            line_number=u.line_number,
            expression=u.expression,
            reason=u.reason
        ) for u in result.unresolved_calls
    ]
    session.add_all(unresolved_records)

    # We do not commit here. The caller (API route) should commit.

def get_analysis(session: Session, analysis_id: str) -> AnalysisRecord | None:
    return session.query(AnalysisRecord).filter(AnalysisRecord.id == analysis_id).first()

def get_entities(session: Session, analysis_id: str) -> list[EntityRecord]:
    return session.query(EntityRecord).filter(EntityRecord.analysis_id == analysis_id).all()

def get_relationships(session: Session, analysis_id: str) -> list[RelationshipRecord]:
    return session.query(RelationshipRecord).filter(RelationshipRecord.analysis_id == analysis_id).all()

def get_unresolved_calls(session: Session, analysis_id: str) -> list[UnresolvedCallRecord]:
    return session.query(UnresolvedCallRecord).filter(UnresolvedCallRecord.analysis_id == analysis_id).all()

def analysis_exists(session: Session, analysis_id: str) -> bool:
    return session.query(AnalysisRecord).filter(AnalysisRecord.id == analysis_id).first() is not None

def reconstruct_graph(session: Session, analysis_id: str) -> DependencyGraph:
    graph = DependencyGraph()
    entities = get_entities(session, analysis_id)
    relationships = get_relationships(session, analysis_id)
    
    for e_rec in entities:
        e = Entity(
            id=e_rec.entity_id,
            name=e_rec.name,
            entity_type=e_rec.entity_type,
            file_path=e_rec.file_path,
            line_number=e_rec.line_number,
            parent_id=e_rec.parent_id
        )
        graph.add_node(e)
        
    for r_rec in relationships:
        r = Relationship(
            source_id=r_rec.source_id,
            target_id=r_rec.target_id,
            relationship_type=r_rec.relationship_type
        )
        graph.add_edge(r)
        
    return graph
