"""
Routes: Runtime Capabilities — Gambit Lab Nocturne (R1.0)
Informa honestamente ao frontend se Gemini LIVE e Pesquisa Web estão disponíveis.
(AUD-01, AUD-03, P0-A, AT-01)
"""
import os
import re
from urllib.parse import urlparse, parse_qs
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from services.api.models.schemas import CapabilitiesResponseSchema

router = APIRouter(prefix="/api/v1", tags=["Capabilities"])


class ApiConfigRequest(BaseModel):
    api_input: str
    model: Optional[str] = None


def get_manager():
    from services.api.main import session_manager
    return session_manager


@router.get("/capabilities", response_model=CapabilitiesResponseSchema)
def get_capabilities(manager=Depends(get_manager)):
    return manager.get_capabilities()


@router.post("/config/api", response_model=CapabilitiesResponseSchema)
def configure_api(payload: ApiConfigRequest, manager=Depends(get_manager)):
    raw = (payload.api_input or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Informe o link da API ou a chave de acesso da IA.")

    extracted_key = ""
    extracted_model = (payload.model or "").strip()
    custom_url = ""

    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        qs = parse_qs(parsed.query)
        if "key" in qs and qs["key"]:
            extracted_key = qs["key"][0].strip()
        m_match = re.search(r"/models/([a-zA-Z0-9._\-]+)", parsed.path)
        if m_match and not extracted_model:
            extracted_model = m_match.group(1)
        if ":generateContent" in parsed.path or not extracted_key:
            custom_url = raw
    else:
        extracted_key = raw

    if extracted_key:
        os.environ["GEMINI_API_KEY"] = extracted_key
        manager.gemini.api_key = extracted_key
    if custom_url:
        os.environ["GEMINI_API_URL"] = custom_url
        manager.gemini.custom_api_url = custom_url
    else:
        os.environ.pop("GEMINI_API_URL", None)
        manager.gemini.custom_api_url = ""

    if not extracted_model:
        extracted_model = os.environ.get("GEMINI_MODEL", "").strip() or "gemini-3.5-flash-lite"
    os.environ["GEMINI_MODEL"] = extracted_model
    os.environ["GAMBIT_FORCE_DEMO"] = "0"
    manager.gemini.force_demo = False
    manager.gemini.model = extracted_model
    manager.gemini.refresh_from_env()

    return manager.get_capabilities()


