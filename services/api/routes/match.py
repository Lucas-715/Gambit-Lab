"""
Routes: Research Match (v2.2) — Geração de Partida Completa Pró vs Contra, Dossiês por Peça e Replay Auditável.
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from services.api.agents.gemini_adapter import BudgetExceededError, ProviderUnavailableError
from services.api.match.orchestrator import MatchStateConflictError
from services.api.models.schemas import (
    PieceDossierSchema,
    ResearchMatchStateSchema,
    ResumeMatchRequest,
    RunMatchRequest,
)

router = APIRouter(prefix="/api/v1/sessions", tags=["Research Match"])


def get_manager():
    from services.api.main import session_manager
    return session_manager


@router.post("/{session_id}/match/stage", response_model=ResearchMatchStateSchema)
def advance_match_stage(
    session_id: str,
    req: Optional[RunMatchRequest] = Body(default=None),
    manager=Depends(get_manager),
):
    """Executa o próximo estágio (1..7) da partida completa e retorna o progresso real."""
    try:
        depth = req.depth if req else None
        return manager.match_orchestrator.run_next_stage(session_id, depth=depth)
    except KeyError as ke:
        raise HTTPException(status_code=404, detail=str(ke))
    except ProviderUnavailableError as pue:
        raise HTTPException(status_code=pue.status_code, detail=str(pue))
    except BudgetExceededError as bee:
        raise HTTPException(status_code=429, detail=str(bee))


@router.post("/{session_id}/match", response_model=ResearchMatchStateSchema)
def run_complete_match(
    session_id: str,
    req: Optional[RunMatchRequest] = Body(default=None),
    manager=Depends(get_manager),
):
    """Executa todos os estágios (1..7) até a conclusão da partida completa e entrega o replay auditável."""
    try:
        depth = req.depth if req else None
        return manager.match_orchestrator.run_full_match(session_id, depth=depth)
    except KeyError as ke:
        raise HTTPException(status_code=404, detail=str(ke))
    except ProviderUnavailableError as pue:
        raise HTTPException(status_code=pue.status_code, detail=str(pue))
    except BudgetExceededError as bee:
        raise HTTPException(status_code=429, detail=str(bee))


@router.post("/{session_id}/match/resume", response_model=ResearchMatchStateSchema)
def resume_match(
    session_id: str,
    req: Optional[ResumeMatchRequest] = Body(default=None),
    manager=Depends(get_manager),
):
    """Retoma partida interrompida por orçamento (BUDGET_EXHAUSTED), ampliando o orçamento de lances."""
    try:
        return manager.match_orchestrator.resume_match(session_id, extra_plies=req.extra_plies if req else None)
    except KeyError as ke:
        raise HTTPException(status_code=404, detail=str(ke))
    except MatchStateConflictError as mce:
        raise HTTPException(status_code=409, detail=str(mce))
    except ProviderUnavailableError as pue:
        raise HTTPException(status_code=pue.status_code, detail=str(pue))
    except BudgetExceededError as bee:
        raise HTTPException(status_code=429, detail=str(bee))


@router.get("/{session_id}/match", response_model=ResearchMatchStateSchema)
def get_match_status(
    session_id: str,
    manager=Depends(get_manager),
):
    """Retorna o estado atual do Research Match (estágios, peças, timeline e conclusão)."""
    try:
        return manager.match_orchestrator.get_match_state(session_id)
    except KeyError as ke:
        raise HTTPException(status_code=404, detail=str(ke))


@router.get("/{session_id}/pieces", response_model=List[PieceDossierSchema])
def list_piece_dossiers(
    session_id: str,
    viewer_side: Optional[str] = Query(default=None, description="white | black (aplica redação pré-término)"),
    manager=Depends(get_manager),
):
    """Lista os dossiês argumentativos e artefatos de cada peça/grupo com respeito ao isolamento de preparação."""
    try:
        return manager.match_orchestrator.get_pieces_for_viewer(session_id, viewer_side=viewer_side)
    except KeyError as ke:
        raise HTTPException(status_code=404, detail=str(ke))

