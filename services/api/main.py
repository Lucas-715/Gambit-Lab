"""
Gambit Lab Nocturne (2.1) — FastAPI Server Entrypoint
API determinística e auditável para raciocínio multiagente orientado por jogos (Xadrez e Go).
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from services.api.storage.session_manager import SessionManager
from services.api.routes.capabilities import router as capabilities_router
from services.api.routes.sessions import router as sessions_router
from services.api.routes.artifacts import router as artifacts_router
from services.api.routes.fusion import router as fusion_router
from services.api.routes.replay import router as replay_router
from services.api.routes.reports import router as reports_router

app = FastAPI(
    title="Gambit Lab Nocturne API",
    description="Framework multiagente baseado em Xadrez e Go para Pesquisa, Debate e Auditoria com verificação epistêmica.",
    version="2.1.0-nocturne",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

session_manager = SessionManager()

app.include_router(capabilities_router)
app.include_router(sessions_router)
app.include_router(artifacts_router)
app.include_router(fusion_router)
app.include_router(replay_router)
app.include_router(reports_router)


@app.get("/health", tags=["Health"])
def health_check():
    caps = session_manager.get_capabilities()
    return {
        "status": "healthy",
        "app": "Gambit Lab Nocturne",
        "version": "2.1.0-nocturne",
        "demo_mode": not caps["gemini"]["live_allowed"],
        "gemini": caps["gemini"],
        "web_search": caps["web_search"],
        "supported_games": ["chess", "go"],
        "supported_modes": ["research", "debate", "audit"],
        "supported_policies": ["OWN_ONLY", "WEB_ONLY", "HYBRID"],
        "fusion_enabled": True,
    }


web_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "apps", "web"))
if os.path.exists(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("services.api.main:app", host="0.0.0.0", port=8000, reload=True)
