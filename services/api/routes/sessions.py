"""
Routes: Sessions Lifecycle & Actions — Gambit Lab 2.0
"""
from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Optional, List, Dict, Any
from services.api.models.schemas import (
    CreateSessionRequest,
    SessionResponseSchema,
    SubmitActionRequest,
    ActionResponseSchema
)
from services.api.storage.event_store import ConcurrencyConflictError

router = APIRouter(prefix="/api/v1/sessions", tags=["Sessions"])


def get_manager():
    from services.api.main import session_manager
    return session_manager


@router.post("", response_model=Dict[str, Any])
def create_session(req: CreateSessionRequest, manager=Depends(get_manager)):
    return manager.create_session(req)


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


@router.post("/{session_id}/actions", response_model=ActionResponseSchema)
def submit_action(
    session_id: str,
    req: SubmitActionRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    manager=Depends(get_manager)
):
    try:
        return manager.submit_action(
            session_id=session_id,
            expected_version=req.expected_version,
            action=req.action,
            idempotency_key=idempotency_key
        )
    except ConcurrencyConflictError as cce:
        raise HTTPException(status_code=409, detail=str(cce))
    except KeyError:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")


@router.get("/{session_id}/budget")
def get_budget(session_id: str, manager=Depends(get_manager)):
    sess = manager.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    return sess["budget"]

