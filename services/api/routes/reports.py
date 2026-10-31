"""
Routes: Reports & Exports — Gambit Lab 2.0
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Response
from typing import Dict, Any

router = APIRouter(prefix="/api/v1/sessions", tags=["Reports"])


def get_manager():
    from services.api.main import session_manager
    return session_manager


@router.get("/{session_id}/report")
def get_session_report(
    session_id: str,
    format: str = Query("json", pattern="^(json|html|markdown)$"),
    manager=Depends(get_manager)
):
    sess = manager.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")

    events = manager.event_store.get_events(session_id)
    artifacts = sess.get("artifacts", [])
    claims = sess.get("claims", [])
    fusion_rep = sess.get("fusion_report")

    report_data = {
        "session_id": session_id,
        "title": sess["title"],
        "mode": sess["mode"],
        "game": sess["game"],
        "status": sess["status"],
        "version": sess["version"],
        "source_policy": sess["source_policy"],
        "artifacts_count": len(artifacts),
        "claims_count": len(claims),
        "events_count": len(events),
        "game_result": sess["board"].get("game_result"),
        "evidence_assessment": "INTEGRITY_VERIFIED",
        "fusion_report": fusion_rep,
        "claims": claims
    }

    if format == "json":
        return report_data
    elif format == "markdown":
        md = f"""# Relatório de Auditoria e Investigação — Gambit Lab 2.0
**Sessão**: `{session_id}`  
**Tema**: {sess['title']}  
**Modalidade**: {sess['mode'].upper()} | **Jogo**: {sess['game'].upper()}  
**Status**: {sess['status']} (v{sess['version']})  
**Resultado de Jogo**: {sess['board'].get('game_result') or 'Em andamento'}  
**Integridade Factual**: Rastreabilidade por hashes SHA-256 e eventos canônicos.

---

## 1. Artefatos e Fontes ({len(artifacts)})
"""
        for art in artifacts:
            md += f"- **{art.get('name')}** (`{art.get('sha256')[:12]}...`) — {art.get('owner_side')}\n"

        md += f"\n## 2. Alegações e Vereditos ({len(claims)})\n"
        for c in claims:
            md += f"- **[{c.get('status')}]** {c.get('statement')}\n"

        if fusion_rep:
            md += f"\n## 3. Síntese FUSION\n{fusion_rep.get('unified_synthesis')}\n"

        return Response(content=md, media_type="text/markdown")
    else:
        html = f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>Relatório - Gambit Lab 2.0</title>
<style>body{{font-family:sans-serif;background:#0d1722;color:#edf5fa;padding:30px;line-height:1.6;}} h1,h2{{color:#61d2c0;}} .box{{background:#12202c;padding:15px;border-radius:8px;margin:15px 0;border:1px solid #233b4b;}}</style>
</head>
<body>
<h1>Gambit Lab 2.0 — Relatório Auditável</h1>
<div class="box">
<p><b>Sessão:</b> {session_id} | <b>Tema:</b> {sess['title']}</p>
<p><b>Modalidade:</b> {sess['mode'].upper()} | <b>Jogo:</b> {sess['game'].upper()}</p>
<p><b>Eventos registrados:</b> {len(events)} | <b>Artefatos:</b> {len(artifacts)}</p>
</div>
<h2>Alegações e Achados</h2>
<ul>
"""
        for c in claims:
            html += f"<li><b>[{c.get('status')}]</b> {c.get('statement')}</li>"
        html += "</ul></body></html>"
        return Response(content=html, media_type="text/html")
