from pydantic import BaseModel
from typing import Optional, List

class AnalyzeRequest(BaseModel):
    repository_path: str

class AnalysisSummaryResponse(BaseModel):
    analysis_id: str
    repository_path: str
    total_entities: int
    total_relationships: int
    status: str
    parse_errors: Optional[List[List[str]]] = None
    packages: Optional[List[str]] = None

class EntitySchema(BaseModel):
    id: str
    name: str
    entity_type: str
    file_path: str
    line_number: int
    parent_id: Optional[str] = None

class RelationshipSchema(BaseModel):
    source_id: str
    target_id: str
    relationship_type: str

class ImpactReportSchema(BaseModel):
    selected_entity: EntitySchema
    direct_dependencies: List[EntitySchema]
    indirect_dependencies: List[EntitySchema]
    direct_dependents: List[EntitySchema]
    indirect_dependents: List[EntitySchema]

class UnresolvedCallSchema(BaseModel):
    file_path: str
    line_number: int
    expression: str
    reason: str

class GitImpactRequest(BaseModel):
    base_ref: Optional[str] = None
    target_ref: Optional[str] = None

class FileChangeSchema(BaseModel):
    change_type: str
    path: str
    old_path: Optional[str] = None

class GitImpactResponse(BaseModel):
    changes: List[FileChangeSchema]
    mapped_entities: List[EntitySchema]
    potentially_affected_dependents: List[EntitySchema]