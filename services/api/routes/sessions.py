"""
Routes: Sessions Lifecycle, Investigation Advance & Actions — Gambit Lab Nocturne (R1.0)
"""
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from services.api.models.schemas import (
    CreateSessionRequest,
    SubmitActionRequest,
    ActionResponseSchema,
    AdvanceSessionRequest,
    AdvanceSessionResponse,
)
from services.api.storage.event_store import ConcurrencyConflictError
from services.api.storage.session_manager import SessionStateConflictError
from services.api.agents.gemini_adapter import BudgetExceededError, ProviderUnavailableError
from services.api.agents.web_search_adapter import WebSearchUnavailableError, SSRFBlockedError

router = APIRouter(prefix="/api/v1/sessions", tags=["Sessions"])


def get_manager():
    from services.api.main import session_manager
    return session_manager


class RegisterClaimRequest(BaseModel):
    statement: str
    artifact_id: Optional[str] = None
    quote_text: Optional[str] = None
    author_agent: str = "agent_pesquisador"


@router.post("", response_model=Dict[str, Any])
def create_session(req: CreateSessionRequest, manager=Depends(get_manager)):
    try:
        return manager.create_session(req)
    except WebSearchUnavailableError as ws_err:
        raise HTTPException(status_code=503, detail=str(ws_err))


@router.get("", response_model=List[Dict[str, Any]])
def list_sessions(manager=Depends(get_manager)):
    return manager.list_sessions()


@router.get("/{session_id}", response_model=Dict[str, Any])
def get_session(session_id: str, manager=Depends(get_manager)):
    sess = manager.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    return sess


@router.post("/{session_id}/lock", response_model=Dict[str, Any])
def lock_session(session_id: str, manager=Depends(get_manager)):
    try:
        return manager.lock_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")


@router.post("/{session_id}/start", response_model=Dict[str, Any])
def start_session(session_id: str, manager=Depends(get_manager)):
    try:
        return manager.start_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")


@router.post("/{session_id}/pause", response_model=Dict[str, Any])
def pause_session(session_id: str, manager=Depends(get_manager)):
    try:
        return manager.pause_session(session_id)
    except SessionStateConflictError as sce:
        raise HTTPException(status_code=409, detail=str(sce))
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")


@router.post("/{session_id}/resume", response_model=Dict[str, Any])
def resume_session(session_id: str, manager=Depends(get_manager)):
    try:
        return manager.resume_session(session_id)
    except SessionStateConflictError as sce:
        raise HTTPException(status_code=409, detail=str(sce))
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")


@router.post("/{session_id}/cancel", response_model=Dict[str, Any])
def cancel_session(session_id: str, manager=Depends(get_manager)):
    try:
        return manager.cancel_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")


@router.post("/{session_id}/advance", response_model=AdvanceSessionResponse)
def advance_session(
    session_id: str,
    req: AdvanceSessionRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    manager=Depends(get_manager),
):
    try:
        return manager.advance_investigation(
            session_id=session_id,
            req=req,
            idempotency_key=idempotency_key,
        )
    except ConcurrencyConflictError as cce:
        raise HTTPException(status_code=409, detail=str(cce))
    except SessionStateConflictError as sce:
        raise HTTPException(status_code=409, detail=str(sce))
    except BudgetExceededError as bee:
        raise HTTPException(status_code=429, detail=str(bee))
    except ProviderUnavailableError as pue:
        raise HTTPException(status_code=pue.status_code, detail=str(pue))
    except WebSearchUnavailableError as wsue:
        raise HTTPException(status_code=503, detail=str(wsue))
    except SSRFBlockedError as ssrf_err:
        raise HTTPException(status_code=403, detail=str(ssrf_err))
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")


@router.post("/{session_id}/claims", response_model=Dict[str, Any])
def register_claim(
    session_id: str,
    req: RegisterClaimRequest,
    manager=Depends(get_manager),
):
    try:
        return manager.register_claim_with_citation(
            session_id=session_id,
            statement=req.statement,
            artifact_id=req.artifact_id,
            quote_text=req.quote_text,
            author_agent=req.author_agent,
        )
    except KeyError as ke:
        raise HTTPException(status_code=404, detail=str(ke))


@router.post("/{session_id}/actions", response_model=ActionResponseSchema)
def submit_action(
    session_id: str,
    req: SubmitActionRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    manager=Depends(get_manager),
):
    try:
        return manager.submit_action(
            session_id=session_id,
            expected_version=req.expected_version,
            action=req.action,
            idempotency_key=idempotency_key,
        )
    except ConcurrencyConflictError as cce:
        raise HTTPException(status_code=409, detail=str(cce))
    except SessionStateConflictError as sce:
        raise HTTPException(status_code=409, detail=str(sce))
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")


@router.get("/{session_id}/budget")
def get_budget(session_id: str, manager=Depends(get_manager)):
    sess = manager.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    return sess["budget"]
