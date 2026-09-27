import uuid
from fastapi import APIRouter, HTTPException, Query
from app.api.schemas import (
    AnalyzeRequest, AnalysisSummaryResponse, EntitySchema, RelationshipSchema, ImpactReportSchema
)
from app.api.store import save_analysis, get_analysis, analysis_exists
from app.analysis.engine import analyze_repository
from app.analysis.impact import analyze_impact

router = APIRouter()

@router.get("/health")
def health_check():
    return {"status": "ok"}

@router.post("/analyze", response_model=AnalysisSummaryResponse)
def analyze(req: AnalyzeRequest):
    try:
        result = analyze_repository(req.repository_path)
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="Repository path does not exist")
    except NotADirectoryError:
        raise HTTPException(status_code=400, detail="Path is not a directory")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    analysis_id = str(uuid.uuid4())
    save_analysis(analysis_id, result)
    
    return AnalysisSummaryResponse(
        analysis_id=analysis_id,
        repository_path=result.repository_path,
        total_entities=len(result.entities),
        total_relationships=len(result.relationships),
        status="success"
    )

@router.get("/analysis/{analysis_id}", response_model=AnalysisSummaryResponse)
def get_analysis_summary(analysis_id: str):
    result = get_analysis(analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    return AnalysisSummaryResponse(
        analysis_id=analysis_id,
        repository_path=result.repository_path,
        total_entities=len(result.entities),
        total_relationships=len(result.relationships),
        status="success",
        parse_errors=result.parse_errors,
        packages=result.packages
    )

@router.get("/analysis/{analysis_id}/entities", response_model=list[EntitySchema])
def get_entities(analysis_id: str):
    result = get_analysis(analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    return [
        EntitySchema(
            id=e.id,
            name=e.name,
            entity_type=e.entity_type,
            file_path=e.file_path,
            line_number=e.line_number,
            parent_id=e.parent_id
        )
        for e in result.entities
    ]

@router.get("/analysis/{analysis_id}/relationships", response_model=list[RelationshipSchema])
def get_relationships(analysis_id: str):
    result = get_analysis(analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    return [
        RelationshipSchema(
            source_id=r.source_id,
            target_id=r.target_id,
            relationship_type=r.relationship_type
        )
        for r in result.relationships
    ]

@router.get("/analysis/{analysis_id}/impact", response_model=ImpactReportSchema)
def get_impact(analysis_id: str, entity_id: str = Query(..., description="The ID of the entity to analyze")):
    result = get_analysis(analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    if not result.graph.has_node(entity_id):
        raise HTTPException(status_code=404, detail="Unknown entity_id")
    
    try:
        report = analyze_impact(result.graph, entity_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown entity_id")
    
    def to_schema(e):
        return EntitySchema(
            id=e.id,
            name=e.name,
            entity_type=e.entity_type,
            file_path=e.file_path,
            line_number=e.line_number,
            parent_id=e.parent_id
        )
        
    return ImpactReportSchema(
        selected_entity=to_schema(report.selected_entity),
        direct_dependencies=[to_schema(e) for e in report.direct_dependencies],
        indirect_dependencies=[to_schema(e) for e in report.indirect_dependencies],
        direct_dependents=[to_schema(e) for e in report.direct_dependents],
        indirect_dependents=[to_schema(e) for e in report.indirect_dependents]
    )
