"""
Routes: Events & Deterministic Replay — Gambit Lab Nocturne (R1.0)
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional

router = APIRouter(prefix="/api/v1/sessions", tags=["Events & Replay"])


def get_manager():
    from services.api.main import session_manager
    return session_manager


@router.get("/{session_id}/events", response_model=List[Dict[str, Any]])
def get_session_events(
    session_id: str,
    after: int = Query(0, ge=0),
    manager=Depends(get_manager),
):
    sess = manager.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    return manager.event_store.get_events(session_id, after_seq=after)


@router.get("/{session_id}/replay", response_model=Dict[str, Any])
def replay_session(
    session_id: str,
    up_to_seq: Optional[int] = Query(None, ge=1),
    manager=Depends(get_manager),
):
    sess = manager.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    try:
        return manager.event_store.replay_session(
            session_id,
            game_type=sess["game"],
            up_to_seq=up_to_seq,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
