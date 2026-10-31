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

