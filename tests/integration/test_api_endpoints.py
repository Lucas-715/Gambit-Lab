"""
Integration tests for FastAPI Endpoints & The 6 Combinations (AC-01 to AC-06, AC-07, AC-18)
"""
import pytest
from starlette.testclient import TestClient
from services.api.main import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "chess" in data["supported_games"]
    assert "go" in data["supported_games"]


def test_ac01_research_in_chess():
    """AC-01: Selecionar pesquisa/xadrez; passo gera lance legal e claim vinculado."""
    # 1. Cria sessão
    resp = client.post("/api/v1/sessions", json={
        "title": "Investigação sobre IA explicável",
        "mode": "research",
        "game": "chess",
        "source_policy": "own_only"
    })
    assert resp.status_code == 200
    sess = resp.json()
    sess_id = sess["id"]
    assert sess["mode"] == "research"
    assert sess["game"] == "chess"
    assert sess["version"] == 1

    # 2. Executa lance legal com claim
    action_resp = client.post(
        f"/api/v1/sessions/{sess_id}/actions",
        json={
            "expected_version": 1,
            "action": {
                "kind": "move_piece",
                "coord": "d2d4",
                "claim_id": "claim_d4_01"
            }
        }
    )
    assert action_resp.status_code == 200
    act_data = action_resp.json()
    assert act_data["accepted"]
    assert act_data["version"] == 2
    assert act_data["engine_result"] == "LEGAL"
    assert act_data["next_to_move"] == "black"


def test_ac02_research_in_go():
    """AC-02: Selecionar pesquisa/go; pedras legais e mapa de cobertura separado de território."""
    resp = client.post("/api/v1/sessions", json={
        "title": "Mapeamento temático de conformidade",
        "mode": "research",
        "game": "go",
        "source_policy": "own_only"
    })
    assert resp.status_code == 200
    sess_id = resp.json()["id"]

    # Pretas começam no Go (RN-03, RF-14)
    action_resp = client.post(
        f"/api/v1/sessions/{sess_id}/actions",
        json={
            "expected_version": 1,
            "action": {
                "kind": "place_stone",
                "coord": "D4",
                "claim_id": "claim_go_d4"
            }
        }
    )
    assert action_resp.status_code == 200
    act_data = action_resp.json()
    assert act_data["accepted"]
    assert act_data["next_to_move"] == "white"
    assert len(act_data["board"]["stones"]) == 1


def test_ac03_debate_in_chess_conditional_capture():
    """AC-03: Debate em Xadrez; brancas iniciam; captura condicionada."""
    resp = client.post("/api/v1/sessions", json={
        "title": "Debate sobre segurança de APIs",
        "mode": "debate",
        "game": "chess"
    })
    sess_id = resp.json()["id"]

    # 1. e2e4 (Brancas)
    client.post(f"/api/v1/sessions/{sess_id}/actions", json={
        "expected_version": 1,
        "action": {"kind": "move_piece", "coord": "e2e4"}
    })
    # 2. d7d5 (Pretas)
    client.post(f"/api/v1/sessions/{sess_id}/actions", json={
        "expected_version": 2,
        "action": {"kind": "move_piece", "coord": "d7d5"}
    })
    # 3. e4d5 (Tentativa de captura pelas Brancas sem prova refutando o alvo)
    # Conforme AC-03 e RN-06: tentativa de captura sem veredito REFUTED é rejeitada!
    cap_resp = client.post(f"/api/v1/sessions/{sess_id}/actions", json={
        "expected_version": 3,
        "action": {"kind": "move_piece", "coord": "e4d5", "refutation_target_id": "claim_d5"}
    })
    assert cap_resp.status_code == 200
    res_json = cap_resp.json()
    assert not res_json["accepted"]  # Bloqueado epistemologicamente (AC-03)
    assert res_json["engine_result"] == "IMPASSE_DA_VARIANTE"
    assert "REFUTED" in res_json["error"]


def test_ac04_debate_in_go():
    """AC-04: Debate em Go; pretas iniciam; captura espacial preserva histórico."""
    resp = client.post("/api/v1/sessions", json={
        "title": "Debate Go sobre limites de inferência",
        "mode": "debate",
        "game": "go"
    })
    sess_id = resp.json()["id"]

    res = client.post(f"/api/v1/sessions/{sess_id}/actions", json={
        "expected_version": 1,
        "action": {"kind": "place_stone", "coord": "E5", "claim_id": "claim_e5"}
    })
    assert res.status_code == 200
    assert res.json()["accepted"]


def test_ac05_audit_in_chess():
    """AC-05: Auditoria em Xadrez; peças representam controles de risco."""
    resp = client.post("/api/v1/sessions", json={
        "title": "Auditoria de Controles ISO 27001",
        "mode": "audit",
        "game": "chess"
    })
    sess_id = resp.json()["id"]
    res = client.post(f"/api/v1/sessions/{sess_id}/actions", json={
        "expected_version": 1,
        "action": {"kind": "move_piece", "coord": "d2d4", "claim_id": "ctrl_auth_01"}
    })
    assert res.status_code == 200
    assert res.json()["accepted"]


def test_ac06_audit_in_go():
    """AC-06: Auditoria em Go; regiões representam domínios auditados."""
    resp = client.post("/api/v1/sessions", json={
        "title": "Auditoria de Conformidade em Nuvem",
        "mode": "audit",
        "game": "go"
    })
    sess_id = resp.json()["id"]
    res = client.post(f"/api/v1/sessions/{sess_id}/actions", json={
        "expected_version": 1,
        "action": {"kind": "place_stone", "coord": "C3", "claim_id": "audit_c3"}
    })
    assert res.status_code == 200
    assert res.json()["accepted"]


def test_optimistic_concurrency_conflict():
    """RNF-17: Falha de concorrência com expected_version incorreto produz HTTP 409."""
    resp = client.post("/api/v1/sessions", json={
        "title": "Teste de concorrência",
        "mode": "research",
        "game": "chess"
    })
    sess_id = resp.json()["id"]

    # Envia versão 999 quando a atual é 1
    err_resp = client.post(f"/api/v1/sessions/{sess_id}/actions", json={
        "expected_version": 999,
        "action": {"kind": "move_piece", "coord": "e2e4"}
    })
    assert err_resp.status_code == 409
    assert "conflito" in err_resp.json()["detail"].lower()


def test_fusion_endpoint_and_synthesis():
    """AC-07: FUSION com dois gambitos e geração de relatório de síntese."""
    resp = client.post("/api/v1/sessions", json={
        "title": "Qual a melhor arquitetura para IA segura?",
        "mode": "research",
        "game": "chess"
    })
    sess_id = resp.json()["id"]

    fusion_resp = client.post(f"/api/v1/sessions/{sess_id}/research/fusion", json={
        "strategies": ["queen", "king"]
    })
    assert fusion_resp.status_code == 200
    fdata = fusion_resp.json()
    assert len(fdata["branches"]) == 2
    assert fdata["report"]["deduplicated_sources_count"] >= 1
    assert "Síntese Unificada FUSION" in fdata["report"]["unified_synthesis"]


def test_replay_endpoint():
    """AC-18: Replay reconstrói exatamente o mesmo estado a partir dos eventos."""
    resp = client.post("/api/v1/sessions", json={
        "title": "Teste de Replay",
        "mode": "research",
        "game": "chess"
    })
    sess_id = resp.json()["id"]
    client.post(f"/api/v1/sessions/{sess_id}/actions", json={
        "expected_version": 1,
        "action": {"kind": "move_piece", "coord": "e2e4"}
    })
    client.post(f"/api/v1/sessions/{sess_id}/actions", json={
        "expected_version": 2,
        "action": {"kind": "move_piece", "coord": "e7e5"}
    })

    rep_resp = client.get(f"/api/v1/sessions/{sess_id}/replay")
    assert rep_resp.status_code == 200
    rdata = rep_resp.json()
    assert rdata["events_count"] == 3  # SESSION_CREATED + 2 moves
    assert rdata["board"]["turn"] == "white"
