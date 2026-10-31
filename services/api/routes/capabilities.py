"""
Routes: Runtime Capabilities — Gambit Lab Nocturne (R1.0)
Informa honestamente ao frontend se Gemini LIVE e Pesquisa Web estão disponíveis.
(AUD-01, AUD-03, P0-A, AT-01)
"""
from fastapi import APIRouter, Depends
from services.api.models.schemas import CapabilitiesResponseSchema

router = APIRouter(prefix="/api/v1", tags=["Capabilities"])


def get_manager():
    from services.api.main import session_manager
    return session_manager


@router.get("/capabilities", response_model=CapabilitiesResponseSchema)
def get_capabilities(manager=Depends(get_manager)):
    return manager.get_capabilities()
