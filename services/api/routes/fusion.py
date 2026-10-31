"""
Routes: FUSION Research — Gambit Lab Nocturne (R1.0)
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any
from services.api.agents.gemini_adapter import ProviderUnavailableError, BudgetExceededError

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
    manager=Depends(get_manager),
):
    raw_sess = manager.sessions.get(session_id)
    if not raw_sess:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")

    try:
        full_arts = manager.vault.get_accessible_artifacts_with_content(session_id)
        force_demo = raw_sess.get("execution_mode") == "DEMO_OFFLINE"

        fusion_res = manager.fusion_orchestrator.run_fusion_research(
            session_id=session_id,
            question=raw_sess["title"],
            game=raw_sess["game"],
            strategy_keys=req.strategies,
            artifacts=full_arts,
            budget=raw_sess["budget"],
            force_demo=force_demo,
        )

        raw_sess["branches"] = fusion_res["branches"]
        raw_sess["fusion_report"] = fusion_res["report"]
        raw_sess["claims"].extend(fusion_res["claims"])

        manager._append_session_event(
            session_id=session_id,
            event_type="FUSION_RESEARCH_COMPLETED",
            payload={
                "strategies": req.strategies,
                "deduplicated_sources_count": fusion_res["report"]["deduplicated_sources_count"],
                "divergences_count": len(fusion_res["report"]["divergences"]),
            },
        )

        return fusion_res
    except ProviderUnavailableError as pue:
        raise HTTPException(status_code=pue.status_code, detail=str(pue))
    except BudgetExceededError as bee:
        raise HTTPException(status_code=429, detail=str(bee))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
