"""
tests/integration/test_v25_1_thematic_relevance.py
Testes Obrigatórios da Auditoria v2.5.1:
1. Relevância temática: rejeição estrita de subteses genéricas de TI em investigação eleitoral.
2. Arbitragem rigorosa: impedimento de uso de citação verdadeira, porém irrelevante (ex.: Temer 2016 para Renan 2030), como refutação.
3. Não-vitória automática de duas hipóteses sem evidência (duas fraquezas não geram vencedor).
4. Calibração honesta e individualizada de confiança por peça (sem 48% fixo para todas as 32 peças).
"""
import pytest
from starlette.testclient import TestClient

from services.api.main import app, session_manager
from services.api.match.clash_engine import SemanticClashEngine


@pytest.fixture
def client():
    return TestClient(app)


def test_political_investigation_rejects_it_templates_and_decomposes_electoral_dimensions(client):
    """
    Problema 1: A pergunta 'Renan Santos será presidente do Brasil em 2030?'
    deve gerar dimensões políticas/eleitorais pertinentes, NUNCA templates genéricos de TI (MTTR, supply-chain, etc.).
    """
    create_payload = {
        "title": "Renan Santos será presidente do Brasil em 2030?",
        "game": "chess",
        "mode": "debate",
        "depth": "quick",
    }
    resp = client.post("/api/v1/sessions", json=create_payload)
    assert resp.status_code == 200
    session_id = resp.json()["id"]

    # Executa os 4 estágios de preparação
    for _ in range(4):
        s_resp = client.post(f"/api/v1/sessions/{session_id}/match/stage", json={"depth": "quick"})
        assert s_resp.status_code == 200

    sm = session_manager
    sess = sm.sessions[session_id]
    pieces = sess["research_match"]["pieces"]
    assert len(pieces) == 32

    # Termos proibidos de TI que não possuem relação fundamentada com a eleição
    forbidden_it_terms = [
        "mttr",
        "tempo de mitigação",
        "supply chain",
        "supply-chain",
        "segregação de privilégios",
        "revisão por pares",
        "privilégios excessivos",
        "cobertura de testes",
        "ponto único de falha",
        "spof",
    ]

    claims_text = " ".join(p["claim"].lower() for p in pieces)
    for term in forbidden_it_terms:
        assert term not in claims_text, (
            f"Falha de relevância temática: termo indevido de TI '{term}' encontrado em subtese eleitoral!"
        )

    # Verifica que dimensões eleitorais reais foram atribuídas
    electoral_terms = [
        "eleitoral", "candidatura", "competitividade", "alianças",
        "partidár", "elegibilidade", "voto", "pesquisas"
    ]
    found_electoral = [term for term in electoral_terms if term in claims_text]
    assert len(found_electoral) >= 4, (
        f"Esperadas dimensões temáticas eleitorais, encontradas apenas: {found_electoral}"
    )

    # Verifica calibração honesta de confiança (eliminação de 48% idêntico em todas as 32 peças)
    confidences = [p["confidence_score"] for p in pieces]
    unique_confidences = set(confidences)
    assert len(unique_confidences) > 1, (
        f"Confiança não pode ser padronizada identicamente para todas as 32 peças! Valores: {unique_confidences}"
    )

    # Peças sem fontes devem ser rotuladas como hipóteses abertas honestas
    unsupported_pieces = [p for p in pieces if not p.get("supporting_artifacts")]
    assert len(unsupported_pieces) > 0
    for p in unsupported_pieces:
        assert p["epistemic_status"] == "HYPOTHESIS"
        assert "hipótese a investigar" in p["claim"].lower() or "aguardando" in p["claim"].lower()
        # Confiança de hipótese não comprovada deve ser baixa e honesta (< 0.40)
        assert p["confidence_score"] < 0.40, f"Hipótese não comprovada {p['piece_id']} com confiança inflada: {p['confidence_score']}"


def test_irrelevant_true_quote_cannot_authorize_capture():
    """
    Problema 2: Uma citação verdadeira, porém irrelevante ao tema da disputa
    (ex.: texto de 2016 sobre Michel Temer para contestar eleição de 2030),
    NÃO PODE autorizar captura (deve retornar CONFRONTATION_INCONCLUSIVE).
    """
    engine = SemanticClashEngine()

    attacker = {
        "piece_id": "white_pawn_e2",
        "label": "Peão Branco e2",
        "color": "white",
        "role": "Evidência",
        "claim": "Alegação de viabilidade eleitoral para Renan Santos em 2030.",
        "confidence_score": 0.75,
        "epistemic_status": "SOURCE_VERIFIED",
        "supporting_artifacts": [
            {
                "artifact_id": "art_temer",
                "title": "Governo Michel Temer em 2016",
                "quote_text": "O governo Michel Temer assumiu interinamente a presidência da República em maio de 2016.",
                "verified": True,
            }
        ],
    }

    defender = {
        "piece_id": "black_pawn_d7",
        "label": "Peão Preto d7",
        "color": "black",
        "role": "Crítica",
        "claim": "Hipótese a investigar: Incerteza do cenário eleitoral de 2030 e volatilidade de pesquisas.",
        "confidence_score": 0.22,
        "epistemic_status": "HYPOTHESIS",
        "supporting_artifacts": [],
    }

    res = engine.evaluate_confrontation(
        session_id="test_sess_relevance",
        attacker=attacker,
        defender=defender,
        from_coord="e2",
        to_coord="d7",
        all_pieces=[attacker, defender],
    )

    # A captura NÃO PODE ser autorizada com fonte descontextualizada!
    assert res["verdict"] != "CAPTURE_AUTHORIZED", (
        f"Erro crítico: citação irrelevante de 2016 autorizou captura indevida! Veredito: {res['verdict']}"
    )
    assert res["verdict"] == "CONFRONTATION_INCONCLUSIVE"
    assert "relevância temática" in res["justification"].lower() or "contexto" in res["justification"].lower()


def test_two_unsupported_hypotheses_produce_inconclusive_verdict():
    """
    Problema 2: Duas peças sem evidências comprovadas não geram vencedor automático.
    O confronto deve ser estritamente CONFRONTATION_INCONCLUSIVE, mantendo o defensor no tabuleiro.
    """
    engine = SemanticClashEngine()

    attacker = {
        "piece_id": "white_knight_b1",
        "label": "Cavalo Branco b1",
        "color": "white",
        "role": "Hipótese Tática",
        "claim": "Hipótese a investigar: Tendência de renovação eleitoral, aguardando fundamentação documental.",
        "confidence_score": 0.20,
        "epistemic_status": "HYPOTHESIS",
        "supporting_artifacts": [],
    }

    defender = {
        "piece_id": "black_pawn_c7",
        "label": "Peão Preto c7",
        "color": "black",
        "role": "Hipótese Crítica",
        "claim": "Hipótese a investigar: Polarização política estrutural, aguardando fundamentação documental.",
        "confidence_score": 0.21,
        "epistemic_status": "HYPOTHESIS",
        "supporting_artifacts": [],
    }

    res = engine.evaluate_confrontation(
        session_id="test_sess_hypo",
        attacker=attacker,
        defender=defender,
        from_coord="b1",
        to_coord="c7",
        all_pieces=[attacker, defender],
    )

    assert res["verdict"] == "CONFRONTATION_INCONCLUSIVE"
    assert "Duas hipóteses sem suporte" in res["justification"] or "sem citações" in res["justification"]


def test_pertinent_verified_evidence_authorizes_capture():
    """
    Quando o atacante possui evidência verificada comprovadamente pertinente ao tema,
    a refutação é legítima e autoriza a captura contra uma hipótese não fundamentada.
    """
    engine = SemanticClashEngine()

    attacker = {
        "piece_id": "white_bishop_c1",
        "label": "Bispo Branco c1",
        "color": "white",
        "role": "Plataforma Temática",
        "claim": "Plataforma temática e diálogo com o eleitorado sobre Renan Santos.",
        "confidence_score": 0.78,
        "epistemic_status": "SOURCE_VERIFIED",
        "supporting_artifacts": [
            {
                "artifact_id": "art_renan",
                "title": "Perfil Político e Liderança de Renan Santos",
                "quote_text": "Renan Santos coordenou mobilizações civis e fundou o Movimento Brasil Livre articulando bases do eleitorado.",
                "verified": True,
            }
        ],
    }

    defender = {
        "piece_id": "black_knight_b8",
        "label": "Cavalo Preto b8",
        "color": "black",
        "role": "Crítica",
        "claim": "Hipótese a investigar: Renan Santos não possui capacidade demonstrada de diálogo com o eleitorado.",
        "confidence_score": 0.20,
        "epistemic_status": "HYPOTHESIS",
        "supporting_artifacts": [],
    }

    res = engine.evaluate_confrontation(
        session_id="test_sess_auth_capture",
        attacker=attacker,
        defender=defender,
        from_coord="c1",
        to_coord="b8",
        all_pieces=[attacker, defender],
    )

    assert res["verdict"] == "CAPTURE_AUTHORIZED"
    assert "Refutação demonstrada" in res["justification"]

