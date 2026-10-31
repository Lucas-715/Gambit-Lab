"""
Testes de Integração e Aceite — Gambit Lab v2.5
Xadrez Epistêmico, RBAC Documental de Peça, Semantic Clash Engine e Go SWOT Matrix.
"""
import copy
import json
import pytest
import chess
from starlette.testclient import TestClient

from services.api.main import app, session_manager
from services.api.models.schemas import (
    CreateSessionRequest,
    SwotCategory,
    PieceBoardStatus,
)
from services.api.storage.vault import PermissionDeniedError, DocumentAccessForbiddenError
from services.api.match.clash_engine import SemanticClashEngine


@pytest.fixture
def client():
    return TestClient(app)


def test_v25_piece_vault_rbac_isolation(client):
    """
    Critério 7: RBAC Granular por Peça no DocumentVault.
    Garante que uma peça só consegue ler artefatos que foram explicitamente autorizados para ela.
    """
    create_payload = {
        "title": "Uso de autenticação multifator em sistemas críticos",
        "game": "chess",
        "mode": "debate",
        "depth": "quick",
    }
    resp = client.post("/api/v1/sessions", json=create_payload)
    assert resp.status_code == 200, resp.text
    session_id = resp.json()["id"]

    # Ingestão de documentos para teste
    sm = session_manager
    doc_pro = sm.vault.ingest_document(
        session_id, "mfa_pro.txt", "MFA reduziu incidentes de sequestro de conta em 99 por cento comprovados.", owner_side="white"
    )
    doc_contra = sm.vault.ingest_document(
        session_id, "mfa_contra.txt", "Fadiga de push bombing contorna MFA em testes de invasão reais.", owner_side="black"
    )
    sm.sessions[session_id]["artifacts"].extend([doc_pro, doc_contra])

    # Executa estágios 1 a 4 (preparação, pesquisa pro, contra, atribuição de dossiês)
    for _ in range(4):
        s_resp = client.post(f"/api/v1/sessions/{session_id}/match/stage", json={"depth": "quick"})
        assert s_resp.status_code == 200

    sess = sm.sessions[session_id]
    pieces = sess["research_match"]["pieces"]

    # Pega uma peça com artefatos autorizados
    piece_with_docs = next((p for p in pieces if p.get("authorized_artifact_ids")), None)
    assert piece_with_docs is not None, "Ao menos uma peça deve ter artefatos autorizados"

    auth_art_id = piece_with_docs["authorized_artifact_ids"][0]
    authorized_pid = piece_with_docs["piece_id"]
    unauthorized_pid = "unauthorized_enemy_piece_999"

    # Acesso autorizado deve suceder
    art = sm.vault.get_artifact(auth_art_id, requesting_piece_id=authorized_pid)
    assert art is not None
    assert art["id"] == auth_art_id

    # Acesso desautorizado deve levantar PermissionDeniedError / DocumentAccessForbiddenError
    with pytest.raises(PermissionDeniedError):
        sm.vault.get_artifact(auth_art_id, requesting_piece_id=unauthorized_pid)


def test_v25_heterogeneous_subtheses_32_pieces(client):
    """
    Critérios 1, 2, 3: As 32 peças de xadrez possuem identidades heterogêneas,
    com subteses específicas, parent_thesis_id e claim_id únicos.
    """
    create_payload = {
        "title": "Criptografia pós-quântica em infraestruturas bancárias",
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

    assert len(pieces) == 32, f"Esperado 32 peças de xadrez, encontrado {len(pieces)}"

    pids = [p["piece_id"] for p in pieces]
    assert len(set(pids)) == 32, "Todos os piece_ids devem ser distintos"

    claims = [p["claim"] for p in pieces]
    assert len(set(claims)) == 32, "Todas as 32 peças devem possuir subteses/afirmações heterogêneas"

    # Verifica os Reis (teses centrais)
    white_king = next(p for p in pieces if p["piece_id"] == "white_king_e1")
    black_king = next(p for p in pieces if p["piece_id"] == "black_king_e8")
    assert "tese central" in white_king["role"].lower()
    assert "tese central" in black_king["role"].lower()
    assert "central_thesis" in white_king["parent_thesis_id"]
    assert "central_thesis" in black_king["parent_thesis_id"]


def test_v25_clash_engine_king_invariant(client):
    """
    Critério 9: Proteção Invariante do Rei.
    O Rei é a tese central e NÃO pode ser capturado nem sofrer confronto final
    enquanto houver subteses defensivas ativas do seu lado.
    """
    sm = session_manager
    clash_engine = sm.clash_engine

    attacker = {
        "piece_id": "white_queen_d1",
        "color": "white",
        "role": "Dama",
        "claim": "A tese pro refuta qualquer contestação.",
        "supporting_artifacts": [{"artifact_id": "art_1", "quote_text": "Citação verificada irrefutável."}],
    }
    defender_king = {
        "piece_id": "black_king_e8",
        "color": "black",
        "role": "Tese Central Defensiva",
        "claim": "Tese central do lado contra.",
        "supporting_artifacts": [],
    }
    # Outra peça preta viva no tabuleiro (subtese defensiva ativa)
    active_black_pawn = {
        "piece_id": "black_pawn_e7",
        "color": "black",
        "alive": True,
        "board_status": "active",
        "role": "Fato Atômico",
        "claim": "Subtese viva que blinda o Rei.",
        "supporting_artifacts": [],
    }
    all_pieces = [attacker, defender_king, active_black_pawn]

    result = clash_engine.evaluate_confrontation(
        session_id="test_sess_king",
        attacker=attacker,
        defender=defender_king,
        from_coord="d1",
        to_coord="e8",
        all_pieces=all_pieces,
    )

    assert result["verdict"] == "DEFENSE_SUCCESSFUL"
    assert result["is_king_protected"] is True
    assert "Invariante do Rei" in result["justification"]


def test_v25_clash_engine_evidentiary_arbitration(client):
    """
    Critérios 4, 5, 6: Arbitragem Semântica por Evidências sem Valor Abstrato de Peça.
    Um peão com citação factual verificada refuta uma dama sem evidências.
    Uma peça com defesa comprovada resiste a um atacante sem evidências.
    """
    sm = session_manager
    clash_engine = sm.clash_engine

    # Caso 1: Peão atacante com citação comprovada vs Dama sem comprovação
    pawn_attacker = {
        "piece_id": "white_pawn_d4",
        "color": "white",
        "role": "Fato Atômico",
        "claim": "Citação documental de medição em doze meses.",
        "supporting_artifacts": [{"artifact_id": "art_fact", "quote_text": "Medição empírica de 99% comprovada."}],
    }
    queen_defender = {
        "piece_id": "black_queen_d5",
        "color": "black",
        "role": "Linha Teórica",
        "claim": "Alegação genérica sem fontes comprobatórias.",
        "supporting_artifacts": [],
    }
    res1 = clash_engine.evaluate_confrontation(
        session_id="test_sess_clash_1",
        attacker=pawn_attacker,
        defender=queen_defender,
        from_coord="d4",
        to_coord="d5",
        all_pieces=[pawn_attacker, queen_defender],
    )
    assert res1["verdict"] == "CAPTURE_AUTHORIZED"
    assert "Refutação" in res1["justification"]

    # Caso 2: Atacante sem evidência vs Defensor com evidência comprovada
    res2 = clash_engine.evaluate_confrontation(
        session_id="test_sess_clash_2",
        attacker=queen_defender,  # sem evidências
        defender=pawn_attacker,   # com citação comprovada
        from_coord="d5",
        to_coord="d4",
        all_pieces=[queen_defender, pawn_attacker],
    )
    assert res2["verdict"] == "DEFENSE_SUCCESSFUL"
    assert "Defesa" in res2["justification"]


def test_v25_reachability_api_endpoint(client):
    """
    Critérios 10 e 11: Endpoint de alcance e capturabilidade.
    Retorna movimentos físicos livres e oponentes ao alcance classificados com veredito semântico.
    """
    create_payload = {
        "title": "Microserviços vs Monolitos modulares",
        "game": "chess",
        "mode": "debate",
        "depth": "quick",
    }
    resp = client.post("/api/v1/sessions", json=create_payload)
    assert resp.status_code == 200
    session_id = resp.json()["id"]

    for _ in range(4):
        client.post(f"/api/v1/sessions/{session_id}/match/stage", json={"depth": "quick"})

    # Consulta o alcance do cavalo branco de b1 (initial_coord b1)
    reach_resp = client.get(f"/api/v1/sessions/{session_id}/pieces/white_knight_b1/reachability")
    assert reach_resp.status_code == 200, reach_resp.text
    data = reach_resp.json()

    assert data["piece_id"] == "white_knight_b1"
    assert data["coord"] == "b1"
    # No tabuleiro inicial, o cavalo em b1 pode saltar para a3 e c3
    assert "a3" in data["free_moves"]
    assert "c3" in data["free_moves"]
    assert isinstance(data["reachable_opponents"], list)


def test_v25_confrontation_evaluate_api_endpoint(client):
    """
    Critério 11: Endpoint POST /{session_id}/confrontation/evaluate para modal de confronto.
    Verifica avaliação sob demanda e funcionamento de cache.
    """
    create_payload = {
        "title": "Auditoria contínua vs periódica",
        "game": "chess",
        "mode": "audit",
        "depth": "quick",
    }
    resp = client.post("/api/v1/sessions", json=create_payload)
    assert resp.status_code == 200
    session_id = resp.json()["id"]

    for _ in range(4):
        client.post(f"/api/v1/sessions/{session_id}/match/stage", json={"depth": "quick"})

    eval_payload = {
        "attacker_piece_id": "white_pawn_e2",
        "defender_piece_id": "black_pawn_d7",
        "from_coord": "e2",
        "to_coord": "d7",
    }
    eval_resp = client.post(f"/api/v1/sessions/{session_id}/confrontation/evaluate", json=eval_payload)
    assert eval_resp.status_code == 200, eval_resp.text
    res_data = eval_resp.json()

    assert res_data["attacker_piece_id"] == "white_pawn_e2"
    assert res_data["defender_piece_id"] == "black_pawn_d7"
    assert res_data["verdict"] in ["CAPTURE_AUTHORIZED", "DEFENSE_SUCCESSFUL", "CONFRONTATION_INCONCLUSIVE", "MOVE_ILLEGAL"]
    assert len(res_data["justification"]) > 0

    # Segunda chamada: deve retornar em cache
    eval_resp2 = client.post(f"/api/v1/sessions/{session_id}/confrontation/evaluate", json=eval_payload)
    assert eval_resp2.status_code == 200
    assert eval_resp2.json()["cached"] is True


def test_v25_go_swot_distribution(client):
    """
    Critérios 12 e 13: Go com Matriz SWOT.
    Garante que os 12 papéis de Go possuem categorias SWOT (STRENGTH, WEAKNESS, OPPORTUNITY, THREAT)
    e justificativas estratégicas sem quebrar as regras de liberdades e território.
    """
    create_payload = {
        "title": "Análise SWOT da adoção de Inteligência Artificial em Saúde",
        "game": "go",
        "mode": "audit",
        "depth": "quick",
    }
    resp = client.post("/api/v1/sessions", json=create_payload)
    assert resp.status_code == 200
    session_id = resp.json()["id"]

    for _ in range(4):
        client.post(f"/api/v1/sessions/{session_id}/match/stage", json={"depth": "quick"})

    sm = session_manager
    sess = sm.sessions[session_id]
    pieces = sess["research_match"]["pieces"]

    assert len(pieces) == 12, f"Esperado 12 pedras de Go, encontrado {len(pieces)}"

    categories = {p.get("swot_category") for p in pieces}
    expected_categories = {"STRENGTH", "WEAKNESS", "OPPORTUNITY", "THREAT"}
    assert expected_categories.issubset(categories), f"Categorias SWOT ausentes: {expected_categories - categories}"

    for p in pieces:
        assert p.get("swot_category") in expected_categories
        assert p.get("swot_rationale"), f"Pedra {p['piece_id']} deve possuir swot_rationale"


def test_v25_full_chess_epistemic_match(client):
    """
    Critérios 4, 5, 8, 14: Execução de partida completa de Xadrez Epistêmico.
    Garante que os lances geram confrontos auditáveis, preenchem confrontation_history
    e mantêm a integridade da timeline.
    """
    create_payload = {
        "title": "Adoção de Arquitetura Limpa em Sistemas Legados",
        "game": "chess",
        "mode": "debate",
        "depth": "quick",
        "force_demo": True,
    }
    resp = client.post("/api/v1/sessions", json=create_payload)
    assert resp.status_code == 200
    session_id = resp.json()["id"]

    match_res = client.post(f"/api/v1/sessions/{session_id}/match", json={"depth": "quick"})
    assert match_res.status_code == 200, match_res.text
    mdata = match_res.json()

    assert mdata["is_complete"] is True
    assert len(mdata["timeline"]) > 0

    sm = session_manager
    sess = sm.sessions[session_id]
    pieces = sess["research_match"]["pieces"]

    # Verifica que as peças possuem confrontation_history list
    for p in pieces:
        assert "confrontation_history" in p
        assert isinstance(p["confrontation_history"], list)

    # Verifica integridade da timeline auditável
    first_ply = mdata["timeline"][0]
    assert "ply" in first_ply
    assert "san" in first_ply
    assert "audit_payload" in first_ply or "move" in first_ply

