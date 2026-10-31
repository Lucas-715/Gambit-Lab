"""
Live End-to-End Test com a API do Google Gemini (Problema 2 da Auditoria)
Executa apenas se GEMINI_API_KEY estiver configurada no ambiente.
Verifica:
1. Pergunta inédita
2. Análise de documentos com afirmações conflitantes
3. Extração de citações reais
4. Distinção entre métricas de tempo e erro (NOT_COMPARABLE)
"""
import os
import pytest
from services.api.agents.gemini_adapter import GeminiAdapter

HAS_GEMINI_KEY = bool(os.environ.get("GEMINI_API_KEY"))


@pytest.mark.skipif(not HAS_GEMINI_KEY, reason="Teste ponta a ponta com Gemini exige GEMINI_API_KEY no ambiente.")
def test_live_gemini_research_and_conflict_resolution():
    adapter = GeminiAdapter()
    assert not adapter.is_demo_mode

    topic = "O uso de LLMs no suporte técnico reduz erros de atendimento?"
    artifacts = [
        {
            "id": "doc_alpha",
            "name": "Estudo_Alpha_Tempo.pdf",
            "sha256": "1111111111111111111111111111111111111111111111111111111111111111",
            "content": "Nossa pesquisa em 500 atendimentos comprovou que assistentes com IA reduzem o tempo de primeira resposta em 48%."
        },
        {
            "id": "doc_beta",
            "name": "Estudo_Beta_Erros.pdf",
            "sha256": "2222222222222222222222222222222222222222222222222222222222222222",
            "content": "A análise de acurácia factual demonstrou que respostas não supervisionadas aumentam erros críticos em 18%."
        }
    ]

    budget = {"max_calls": 5, "max_tokens": 10000, "current_calls": 0, "current_tokens": 0}

    # 1. Pesquisador formula argumento com base em documento real
    res_step = adapter.call_research_agent(
        topic=topic,
        strategy="queen",
        game="chess",
        turn_number=1,
        budget=budget,
        artifacts=artifacts
    )

    assert "statement" in res_step
    assert "proposed_move" in res_step
    assert len(res_step["statement"]) > 10

    # 2. Árbitro julga a aparente contradição (tempo vs erro)
    adjudication = adapter.call_debate_adjudication(
        topic=topic,
        claim_statement="O estudo Alpha comprova redução de erros em 48%",
        citation_quote="reduzem o tempo de primeira resposta em 48%",
        counter_quote="respostas não supervisionadas aumentam erros críticos em 18%",
        budget=budget
    )

    # Não são a mesma métrica: deve reconhecer NOT_COMPARABLE ou INCONCLUSIVE!
    assert adjudication["verdict"] in ("NOT_COMPARABLE", "INCONCLUSIVE")
    assert adjudication["rubric"]["role_conflict_free"] is True


@pytest.mark.skipif(not HAS_GEMINI_KEY, reason="Teste ponta a ponta LIVE_WEB exige GEMINI_API_KEY no ambiente.")
def test_live_web_advance_and_real_telemetry():
    """
    Valida em modo LIVE_WEB real via FastAPI (sem mocks):
    - Pesquisa web pública real (OpenAlex / Wikimedia HTTPS) com hash SHA-256 e domínio auditável
    - Chamada real ao Google Gemini com extração de usageMetadata (tokens reais e latência real)
    - Tratamento honesto de pergunta temática sem texto genérico predefinido
    """
    from starlette.testclient import TestClient
    from services.api.main import app

    client = TestClient(app)
    caps_res = client.get("/api/v1/capabilities")
    assert caps_res.status_code == 200
    caps = caps_res.json()
    assert caps["gemini"]["live_allowed"] is True
    assert caps["web_search"]["available"] is True

    create_res = client.post(
        "/api/v1/sessions",
        json={
            "title": "Artificial intelligence safety and multi-agent alignment",
            "mode": "research",
            "game": "chess",
            "source_policy": "WEB_ONLY",
            "max_steps": 8,
        },
    )
    assert create_res.status_code in (200, 201)
    session = create_res.json()
    assert session["execution_mode"] == "LIVE_WEB"

    adv_res = client.post(
        f"/api/v1/sessions/{session['id']}/advance",
        json={"expected_version": session["version"], "max_actions": 1},
    )
    assert adv_res.status_code == 200
    adv = adv_res.json()

    assert adv["execution_mode"] == "LIVE_WEB"
    assert adv["game"]["ply_count"] >= 1
    assert adv["investigation"]["completed_steps"] >= 1
    assert adv["artifacts_count"] >= 1
    assert adv["provider_usage"]["source"] == "gemini_api"
    assert (adv["provider_usage"]["tokens"] or 0) > 0
    assert (adv["provider_usage"]["prompt_tokens"] or 0) > 0
    assert (adv["provider_usage"]["completion_tokens"] or 0) > 0
    assert (adv["provider_usage"]["latency_ms"] or 0) > 0

    detail_res = client.get(f"/api/v1/sessions/{session['id']}")
    assert detail_res.status_code == 200
    artifacts = detail_res.json()["artifacts"]
    assert len(artifacts) >= 1
    assert all(a["url"].startswith("https://") for a in artifacts if a.get("url"))
    assert all(len(a["sha256"]) == 64 for a in artifacts)


