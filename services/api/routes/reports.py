"""
Routes: Reports & Exports — Gambit Lab Nocturne (R1.0)
Relatórios com distinção explícita entre Integridade, Verificação de Fonte, Avaliação de Evidência
e Modo de Execução (DEMO_OFFLINE vs LIVE_*), fiéis ao estado real da sessão (AT-24).
"""
from html import escape
import json

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
    rmatch = manager.sessions[session_id].get("research_match")
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
        "events": events,
        "chain_verified_at_export": manager.event_store.verify_hash_chain(session_id),
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
    else:
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
*Diagnóstico*: {report_data.get('diagnostic_reason') or 'Avalia??o documental pendente.'}

---

## 1. Artefatos e Fontes ({len(artifacts)})
"""
        for art in artifacts:
            src_kind = art.get("source_type", "document").upper()
            url_part = f" — {art.get('canonical_url')}" if art.get("canonical_url") else ""
            md += f"- **[{src_kind}] {art.get('name')}** (`{(art.get('sha256') or '')[:12]}...`) — {art.get('owner_side')}{url_part}\n"

        md += f"\n## 2. Alegações e Vereditos ({len(claims)})\n"
        for c in claims:
            md += f"- **[{c.get('status')}]** {c.get('statement')}\n"
            for cit in c.get("citations", []):
                ver_tag = "VERIFICADA" if cit.get("quote_verified") else "NÃO VERIFICADA"
                md += f"  > *Citação ({ver_tag})*: \"{cit.get('quote_text')}\" ({cit.get('artifact_name')}, {cit.get('page_or_offset')})\n"

        if rmatch and rmatch.get("conclusion"):
            conc = rmatch["conclusion"]
            decision = conc.get('decision') or {}
            if decision:
                md += f"\n## Decisão por critérios\n{decision['answer']}\n\nMétodo: {decision['method']}\n\nEscopo: {decision['scope_rule']}\n"
                for row in decision['criteria']:
                    md += f"\n### {row['id']} — {row['label']}\n**Decisão:** {row['verdict']}\n\n{row['reason']}\n\n**Comparação:** {row['comparison_scope']}\n"
                    for cit in row['citations']:
                        md += f"\n- Peça {cit['piece_id']} | Fonte {cit['artifact_id']} | Trecho: {cit['quote_text']}\n"
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

        if rmatch and rmatch.get("conclusion"):
            conc = rmatch["conclusion"]
            md += "\n## Limitações\n" + "".join(f"- {x}\n" for x in conc.get("limitations", []))
            md += "\n## Próximos passos\n" + "".join(f"- {x}\n" for x in conc.get("next_steps", []))
            md += "\n## Rastreabilidade: alegação → fonte → lance → evento\n"
            for row in conc.get("evidence_trace", []):
                md += f"\n### {row['piece_id']} — {row['side']}\n{row['claim']}\n\nEstado: {row['status']}\n"
                md += f"\nLances: {row['plies']} | Eventos: {row['event_seqs']}\n"
                if not row['evidence']:
                    md += "\nLacuna: nenhuma fonte vinculada.\n"
                for ref in row['evidence']:
                    md += f"\n- Fonte: {ref.get('title')} | ID: {ref.get('artifact_id')} | SHA-256: {ref.get('sha256')}\n"
                    md += f"  URL: {ref.get('url') or 'documento local'} | Citação verificada: {bool(ref.get('verified'))}\n"
                    md += f"  Trecho: {ref.get('quote_text') or 'não informado'}\n"
                finding = row.get('finding')
                if finding:
                    md += f"\nAchado: {finding['finding']}\n\nCritério: {finding['expected_criteria']}\n\nSituação: {finding['compliance_status']} | Risco: {finding['risk_level']}\n"
                    md += f"\nRecomendação: {finding['recommendation']}\n"
        md += f"\n## Integridade na exportação\nCadeia verificada: {report_data['chain_verified_at_export']}\n"
        md += "\nOs hashes permitem detectar alterações; não certificam a veracidade das alegações.\n"
        md += "\n## Eventos para conferência independente\n```json\n" + json.dumps(events, ensure_ascii=False, indent=2) + "\n```\n"

        if fusion_rep:
            md += f"\n## Síntese FUSION\n{fusion_rep.get('unified_synthesis')}\n"

        if format == "markdown":
            return Response(content=md, media_type="text/markdown", headers={
                "Content-Disposition": f'attachment; filename="gambit-{session_id}.md"'
            })
        html = ('<!doctype html><html lang="pt-BR"><meta charset="utf-8">'
                '<title>Relatório Gambit Lab</title><style>body{background:#040405;color:#F4F4F6;max-width:1000px;margin:32px auto;padding:24px;font-family:system-ui}'
                'pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;line-height:1.6}</style>'
                '<body><h1>Relatório auditável</h1><pre>' + escape(md) + '</pre></body></html>')
        return Response(content=html, media_type="text/html")
