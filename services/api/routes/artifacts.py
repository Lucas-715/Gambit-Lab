"""
Routes: Artifacts, Private Vault Isolation & Safe Web Snapshots — Gambit Lab Nocturne (R1.0)
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from services.api.storage.vault import DocumentAccessForbiddenError
from services.api.agents.web_search_adapter import SSRFBlockedError, WebSearchUnavailableError

router = APIRouter(prefix="/api/v1", tags=["Artifacts"])


def get_manager():
    from services.api.main import session_manager
    return session_manager


class UploadArtifactRequest(BaseModel):
    name: str
    content: str
    mime_type: str = "text/plain"
    owner_side: str = "public"


class WebSnapshotRequest(BaseModel):
    url: str
    title: Optional[str] = None


@router.post("/sessions/{session_id}/artifacts", response_model=Dict[str, Any])
def upload_artifact(
    session_id: str,
    req: UploadArtifactRequest,
    manager=Depends(get_manager),
):
    raw_sess = manager.sessions.get(session_id)
    if not raw_sess:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")

    art = manager.vault.ingest_document(
        session_id=session_id,
        name=req.name,
        content=req.content,
        mime_type=req.mime_type,
        owner_side=req.owner_side,
        source_type="document",
    )
    if not any(existing["id"] == art["id"] for existing in raw_sess["artifacts"]):
        raw_sess["artifacts"].append(art)

    resp_art = art.copy()
    resp_art["content_preview"] = art["content"][:240]
    return resp_art


@router.post("/sessions/{session_id}/web-snapshot", response_model=Dict[str, Any])
def ingest_web_snapshot(
    session_id: str,
    req: WebSnapshotRequest,
    manager=Depends(get_manager),
):
    raw_sess = manager.sessions.get(session_id)
    if not raw_sess:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    if raw_sess.get("normalized_source_policy") == "OWN_ONLY":
        raise HTTPException(
            status_code=403,
            detail="OWN_ONLY_POLICY: Ingestão de URLs externas é proibida quando a política da sessão é OWN_ONLY.",
        )

    try:
        snap = manager.web_search_adapter.fetch_url_snapshot(req.url, title=req.title)
        art = manager.vault.ingest_document(
            session_id=session_id,
            name=snap["title"],
            content=snap["content"],
            mime_type="text/plain",
            owner_side="public",
            source_type="web",
            url=snap["url"],
            canonical_url=snap["canonical_url"],
            domain=snap["domain"],
            retrieved_at=snap["retrieved_at"],
            accessible=snap["accessible"],
        )
        if not any(existing["id"] == art["id"] for existing in raw_sess["artifacts"]):
            raw_sess["artifacts"].append(art)
        resp_art = art.copy()
        resp_art["content_preview"] = art["content"][:240]
        del resp_art["content"]
        return resp_art
    except SSRFBlockedError as ssrf_err:
        raise HTTPException(status_code=403, detail=str(ssrf_err))
    except WebSearchUnavailableError as ws_err:
        raise HTTPException(status_code=503, detail=str(ws_err))


@router.get("/sessions/{session_id}/artifacts", response_model=List[Dict[str, Any]])
def list_session_artifacts(
    session_id: str,
    requesting_side: Optional[str] = Query(None),
    manager=Depends(get_manager),
):
    return manager.vault.list_artifacts_for_session(session_id, requesting_side)


@router.get("/sessions/{session_id}/artifacts/{artifact_id}", response_model=Dict[str, Any])
def get_session_artifact_detail(
    session_id: str,
    artifact_id: str,
    requesting_side: Optional[str] = Query(None),
    manager=Depends(get_manager),
):
    try:
        art = manager.vault.get_artifact(artifact_id, requesting_side=requesting_side)
        if art["session_id"] != session_id:
            raise HTTPException(status_code=404, detail="Artefato não pertence a esta sessão.")
        return art
    except DocumentAccessForbiddenError as dafe:
        raise HTTPException(status_code=403, detail=str(dafe))
    except KeyError:
        raise HTTPException(status_code=404, detail="Artefato não encontrado.")


@router.get("/artifacts/{artifact_id}/quote")
def verify_quote(
    artifact_id: str,
    quote: str = Query(...),
    manager=Depends(get_manager),
):
    try:
        verified, offset = manager.vault.find_verified_quote_offset(artifact_id, quote)
        if artifact_id not in manager.vault._artifacts:
            raise KeyError(artifact_id)
        return {
            "artifact_id": artifact_id,
            "quote": quote,
            "verified": verified,
            "offset": offset,
        }
    except KeyError:
        raise HTTPException(status_code=404, detail="Artefato não encontrado.")
