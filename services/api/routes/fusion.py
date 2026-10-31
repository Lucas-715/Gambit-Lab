"""
Routes: FUSION Research — Gambit Lab 2.0
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any

router = APIRouter(prefix="/api/v1/sessions", tags=["FUSION"])


def get_manager():
    from services.api.main import session_manager
    return session_manager


class RunFusionRequest(BaseModel):
    strategies: List[str]


@router.post("/{session_id}/research/fusion", response_model=Dict[str, Any])
def run_fusion(
    session_id: str,
    req: RunFusionRequest,
    manager=Depends(get_manager)
):
    sess = manager.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")

    try:
        fusion_res = manager.fusion_orchestrator.run_fusion_research(
            session_id=session_id,
            question=sess["title"],
            game=sess["game"],
            strategy_keys=req.strategies,
            artifacts=sess["artifacts"],
            budget=sess["budget"]
        )

        sess["branches"] = fusion_res["branches"]
        sess["fusion_report"] = fusion_res["report"]
        sess["claims"].extend(fusion_res["claims"])
        sess["version"] += 1

        # Registra evento de fusão concluída
        manager.event_store.append_event(
            session_id=session_id,
            expected_version=sess["version"] - 1,
            event_type="FUSION_RESEARCH_COMPLETED",
            payload={
                "strategies": req.strategies,
                "deduplicated_sources_count": fusion_res["report"]["deduplicated_sources_count"],
                "divergences_count": len(fusion_res["report"]["divergences"])
            }
        )

        return fusion_res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
