"""
Routes: Artifacts & Document Vault — Gambit Lab 2.0
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from services.api.storage.vault import DocumentAccessForbiddenError

router = APIRouter(prefix="/api/v1", tags=["Artifacts"])


def get_manager():
    from services.api.main import session_manager
    return session_manager


class UploadArtifactRequest(BaseModel):
    name: str
    content: str
    mime_type: str = "text/plain"
    owner_side: str = "public"


@router.post("/sessions/{session_id}/artifacts", response_model=Dict[str, Any])
def upload_artifact(
    session_id: str,
    req: UploadArtifactRequest,
    manager=Depends(get_manager)
):
    sess = manager.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")

    art = manager.vault.ingest_document(
        session_id=session_id,
        name=req.name,
        content=req.content,
        mime_type=req.mime_type,
        owner_side=req.owner_side
    )
    sess["artifacts"].append(art)
    return art


@router.get("/sessions/{session_id}/artifacts", response_model=List[Dict[str, Any]])
def list_session_artifacts(
    session_id: str,
    requesting_side: Optional[str] = Query(None),
    manager=Depends(get_manager)
):
    return manager.vault.list_artifacts_for_session(session_id, requesting_side)


@router.get("/artifacts/{artifact_id}/quote")
def verify_quote(
    artifact_id: str,
    quote: str = Query(...),
    manager=Depends(get_manager)
):
    try:
        exists = manager.vault.verify_quote_exists(artifact_id, quote)
        return {"artifact_id": artifact_id, "quote": quote, "verified": exists}
    except KeyError:
        raise HTTPException(status_code=404, detail="Artefato não encontrado.")
