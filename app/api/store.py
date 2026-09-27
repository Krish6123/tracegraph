from typing import Dict
from app.analysis.engine import AnalysisResult

_store: Dict[str, AnalysisResult] = {}

def save_analysis(analysis_id: str, result: AnalysisResult) -> None:
    _store[analysis_id] = result

def get_analysis(analysis_id: str) -> AnalysisResult | None:
    return _store.get(analysis_id)

def analysis_exists(analysis_id: str) -> bool:
    return analysis_id in _store
