"""
Gambit Lab 2.0 — FastAPI Server Entrypoint
API determinística para raciocínio multiagente orientado por jogos (Xadrez e Go).
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from services.api.storage.session_manager import SessionManager
from services.api.routes.sessions import router as sessions_router
from services.api.routes.artifacts import router as artifacts_router
from services.api.routes.fusion import router as fusion_router
from services.api.routes.replay import router as replay_router
from services.api.routes.reports import router as reports_router

app = FastAPI(
    title="Gambit Lab 2.0 API",
    description="Framework multiagente baseado em Xadrez e Go para Pesquisa, Debate e Auditoria.",
    version="2.0.0"
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instância global do gerenciador de sessões
session_manager = SessionManager()

# Registro de rotas
app.include_router(sessions_router)
app.include_router(artifacts_router)
app.include_router(fusion_router)
app.include_router(replay_router)
app.include_router(reports_router)


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "app": "Gambit Lab 2.0",
        "version": "2.0.0",
        "demo_mode": session_manager.gemini_adapter.is_demo_mode,
        "supported_games": ["chess", "go"],
        "supported_modes": ["research", "debate", "audit"],
        "fusion_enabled": True
    }


# Montagem dos arquivos estáticos da interface web se existirem
web_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "apps", "web"))
if os.path.exists(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("services.api.main:app", host="0.0.0.0", port=8000, reload=True)
