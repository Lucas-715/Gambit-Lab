"""
Routes: Reports & Exports — Gambit Lab Nocturne (R1.0)
Relatórios com distinção explícita entre Integridade, Verificação de Fonte, Avaliação de Evidência
e Modo de Execução (DEMO_OFFLINE vs LIVE_*), fiéis ao estado real da sessão (AT-24).
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Response

router = APIRouter(prefix="/api/v1/sessions", tags=["Reports"])


def get_manager():
    from services.api.main import session_manager
    return session_manager


@router.get("/{session_id}/report")
def get_session_report(
    session_id: str,
    format: str = Query("json", pattern="^(json|html|markdown)$"),
    manager=Depends(get_manager),
):
    sess = manager.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")

    events = manager.event_store.get_events(session_id)
    artifacts = sess.get("artifacts", [])
    claims = sess.get("claims", [])
    judgments = sess.get("judgments", [])
    fusion_rep = sess.get("fusion_report")
    rmatch = sess.get("research_match")
    usage = sess.get("provider_usage") or {}

    report_data = {
        "session_id": session_id,
        "title": sess["title"],
        "mode": sess["mode"],
        "game": sess["game"],
        "status": sess["status"],
        "execution_mode": sess.get("execution_mode", "DEMO_OFFLINE"),
        "version": sess["version"],
        "source_policy": sess["source_policy"],
        "normalized_source_policy": sess.get("normalized_source_policy", "OWN_ONLY"),
        "ply_count": sess.get("ply_count", 0),
        "investigation_step_index": sess.get("investigation_step_index", 0),
        "artifacts_count": len(artifacts),
        "claims_count": len(claims),
        "events_count": len(events),
        "game_result": sess["board"].get("game_result"),
        "integrity_status": sess.get("integrity_status", "NOT_ASSESSED"),
        "source_status": sess.get("source_status", "NO_SOURCES_ATTACHED"),
        "evidence_assessment": sess.get("evidence_assessment", "NOT_ASSESSED"),
        "diagnostic_reason": sess.get("diagnostic_reason"),
        "provider_usage": usage,
        "research_match": rmatch,
        "fusion_report": fusion_rep,
        "artifacts": artifacts,
        "claims": claims,
        "judgments": judgments,
    }

    if format == "json":
        return report_data
    elif format == "markdown":
        tokens_txt = str(usage.get("tokens")) if usage.get("tokens") is not None else "não medido"
        lat_txt = f"{usage.get('latency_ms')} ms" if usage.get("latency_ms") is not None else "não medido"
        md = f"""# Relatório de Auditoria e Investigação — Gambit Lab Nocturne
**Sessão**: `{session_id}`  
**Tema**: {sess['title']}  
**Modalidade**: {sess['mode'].upper()} | **Jogo**: {sess['game'].upper()}  
**Modo de Execução**: `{report_data['execution_mode']}` | **Política de Fontes**: `{report_data['normalized_source_policy']}`  
**Status**: {sess['status']} (v{sess['version']}) | **Lances**: {report_data['ply_count']} | **Etapas**: {report_data['investigation_step_index']}  
**Resultado de Jogo**: {sess['board'].get('game_result') or 'Em andamento'}  
**Telemetria Gemini**: Tokens: {tokens_txt} | Latência última etapa: {lat_txt}  

### Três Dimensões de Verificação Epistêmica:
- **Integridade Criptográfica**: `{report_data['integrity_status']}` (Hashes SHA-256 e Event Store encadeado)
- **Verificação de Fontes**: `{report_data['source_status']}`
- **Avaliação Factual**: `{report_data['evidence_assessment']}`  
*Diagnóstico*: {report_data.get('diagnostic_reason') or 'Conformidade auditada.'}

---

## 1. Artefatos e Fontes ({len(artifacts)})
"""
        for art in artifacts:
            src_kind = art.get("source_type", "document").upper()
            url_part = f" — {art.get('canonical_url')}" if art.get("canonical_url") else ""
            md += f"- **[{src_kind}] {art.get('name')}** (`{art.get('sha256')[:12]}...`) — {art.get('owner_side')}{url_part}\n"

        md += f"\n## 2. Alegações e Vereditos ({len(claims)})\n"
        for c in claims:
            md += f"- **[{c.get('status')}]** {c.get('statement')}\n"
            for cit in c.get("citations", []):
                ver_tag = "VERIFICADA" if cit.get("quote_verified") else "NÃO VERIFICADA"
                md += f"  > *Citação ({ver_tag})*: \"{cit.get('quote_text')}\" ({cit.get('artifact_name')}, {cit.get('page_or_offset')})\n"

        if rmatch and rmatch.get("conclusion"):
            conc = rmatch["conclusion"]
            md += (
                f"\n## Conclusão Final Research Match (Duplo Resultado)\n"
                f"- **Critério de Encerramento**: `{conc.get('termination_criterion')}` — {conc.get('termination_reason')}\n"
                f"- **Resultado Lúdico (Tabuleiro)**: `{conc.get('ludic_result')}` — {conc.get('ludic_score_label')}\n"
                f"- **Resultado Epistêmico (Evidências)**: `{conc.get('epistemic_result')}` — {conc.get('epistemic_verdict_label')}\n"
                f"- **Tese Pró**: {conc.get('pro_thesis')}\n"
                f"- **Tese Contra**: {conc.get('contra_thesis')}\n"
                f"- **Ponto de Virada**: Lance #{conc.get('turning_point_ply') or '-'} — {conc.get('turning_point_summary') or ''}\n\n"
                f"### Síntese Final\n{conc.get('final_synthesis')}\n"
            )

        if fusion_rep:
            md += f"\n## Síntese FUSION\n{fusion_rep.get('unified_synthesis')}\n"

        return Response(content=md, media_type="text/markdown")
    else:
        html = f"""<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>Relatório - Gambit Lab Nocturne</title>
<style>
body{{font-family:Inter,system-ui,sans-serif;background:#040405;color:#F4F4F6;padding:32px;line-height:1.6;max-width:960px;margin:0 auto;}}
h1,h2{{color:#A68DFF;}}
.box{{background:#0B0C0F;padding:18px;border-radius:10px;margin:16px 0;border:1px solid #242630;}}
.badge{{display:inline-block;padding:3px 9px;border-radius:6px;font-size:11px;font-weight:600;margin-right:8px;border:1px solid #242630;background:#121319;color:#F4F4F6;}}
.muted{{color:#9A9BA5;font-size:13px;}}
</style>
</head>
<body>
<h1>Gambit Lab Nocturne — Relatório Auditável</h1>
<div class="box">
<p><b>Sessão:</b> {session_id} | <b>Tema:</b> {sess['title']}</p>
<p><b>Modalidade:</b> {sess['mode'].upper()} | <b>Jogo:</b> {sess['game'].upper()} | <b>Execução:</b> <span class="badge">{report_data['execution_mode']}</span></p>
<p><b>Lances do Jogo:</b> {report_data['ply_count']} | <b>Etapas Investigativas:</b> {report_data['investigation_step_index']} | <b>Eventos:</b> {report_data['events_count']}</p>
<p><b>Integridade:</b> <span class="badge">{report_data['integrity_status']}</span>
   <b>Fontes:</b> <span class="badge">{report_data['source_status']}</span>
   <b>Evidência:</b> <span class="badge">{report_data['evidence_assessment']}</span></p>
<p class="muted">{report_data.get('diagnostic_reason') or ''}</p>
</div>
<h2>Alegações e Vereditos ({len(claims)})</h2>
<ul>
"""
        for c in claims:
            html += f"<li><b>[{c.get('status')}]</b> {c.get('statement')}</li>"
        html += "</ul></body></html>"
        return Response(content=html, media_type="text/html")
