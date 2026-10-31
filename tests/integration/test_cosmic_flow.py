"""
Integration Tests for Gambit Lab Cosmic Workflow & Two-Phase UX Contracts
Verifies the conversational flow: "pergunta primeiro, investigação depois",
artifact vault ingestion, 3-tier verification, FUSION, event replay, and report export.
"""
import pytest
from starlette.testclient import TestClient
from services.api.main import app

client = TestClient(app)


def test_cosmic_frontend_served_with_required_elements():
    """Verifies that the Cosmic UI (index.html) is served at root with both phases (#home & #workspace)."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    # Phase 1: Home Screen
    assert 'id="home"' in html
    assert 'id="question"' in html
    assert 'id="goBtn"' in html
    assert 'id="space"' in html  # Canvas cósmico
    assert 'class="planet p1"' in html  # Planetas flutuantes

    # Phase 2: Workspace Screen
    assert 'id="workspace"' in html
    assert 'id="stage"' in html  # Canvas WebGL 3D
    assert 'id="board2D"' in html  # Tabuleiro 2D acessível
    assert 'id="badgeIntegrity"' in html
    assert 'id="badgeSource"' in html
    assert 'id="badgeEvidence"' in html
    assert 'id="arbitratorCard"' in html
    assert 'id="fusionModal"' in html
    assert 'id="replayModal"' in html


def test_cosmic_unmatched_prompt_has_no_sources_attached():
    """Verifies that a novel question without pre-configured scenario starts with NO_SOURCES_ATTACHED."""
    novel_question = "Análise inédita sobre topologia de redes neurais quânticas"
    resp = client.post("/api/v1/sessions", json={
        "title": novel_question,
        "mode": "research",
        "game": "chess",
        "source_policy": "own_only"
    })
    assert resp.status_code == 200
    sess = resp.json()
    assert sess["integrity_status"] == "INTEGRITY_VERIFIED"
    assert sess["source_status"] == "NO_SOURCES_ATTACHED"
    assert sess["evidence_assessment"] != "SUPPORTED"
    assert sess["artifacts_count"] == 0


def test_cosmic_lifecycle_complete_flow():
    """
    Simulates the full user journey:
    1. Pergunta enviada -> Sessão criada (POST /api/v1/sessions)
    2. Upload de documento com citação para o cofre (POST /api/v1/sessions/{id}/artifacts)
    3. Consulta de citação no cofre
    4. Proposição de lance determinístico (POST /api/v1/sessions/{id}/actions)
    5. Replay no Event Store (GET /api/v1/sessions/{id}/events)
    6. Execução de FUSION Research (POST /api/v1/sessions/{id}/research/fusion)
    7. Exportação de Relatório (GET /api/v1/sessions/{id}/report)
    """
    # 1. Criação a partir da pergunta do compositor
    prompt_question = "Análise e avaliação sobre infraestrutura em nuvem privada"
    create_resp = client.post("/api/v1/sessions", json={
        "title": prompt_question,
        "mode": "research",
        "game": "chess",
        "source_policy": "own_only"
    })
    assert create_resp.status_code == 200
    sess = create_resp.json()
    sess_id = sess["id"]
    assert sess["version"] == 1
    # Sem documentos anexados inicialmente:
    assert sess["integrity_status"] == "INTEGRITY_VERIFIED"
    assert sess["source_status"] == "NO_SOURCES_ATTACHED"
    assert sess["evidence_assessment"] != "SUPPORTED"

    # 2. Upload de documento no cofre
    doc_content = (
        "Diretrizes de Segurança para Nuvem Privada:\n"
        "A integridade operacional exige a separação estrita entre o módulo de proposição "
        "(LLM) e o módulo de validação de regras (motores determinísticos)."
    )
    art_resp = client.post(f"/api/v1/sessions/{sess_id}/artifacts", json={
        "name": "Diretrizes_Nuvem_Privada_2026.txt",
        "content": doc_content,
        "mime_type": "text/plain",
        "owner_side": "public"
    })
    assert art_resp.status_code == 200
    art_data = art_resp.json()
    art_id = art_data["id"]
    assert len(art_data["sha256"]) == 64

    # 3. Consulta de citação exata no cofre
    quote_resp = client.get(
        f"/api/v1/artifacts/{art_id}/quote",
        params={"quote": "separação estrita entre o módulo de proposição"}
    )
    assert quote_resp.status_code == 200
    assert quote_resp.json()["verified"] is True

    # 4. Executa lance legal com alegação vinculada
    action_resp = client.post(f"/api/v1/sessions/{sess_id}/actions", json={
        "expected_version": 1,
        "action": {
            "kind": "move_piece",
            "coord": "d2d4",
            "claim_id": "claim_d4_separacao_estrita"
        }
    })
    assert action_resp.status_code == 200
    act = action_resp.json()
    assert act["accepted"] is True
    assert act["version"] == 2
    assert act["engine_result"] == "LEGAL"

    # 5. Consulta eventos imutáveis para o Replay Stepper
    events_resp = client.get(f"/api/v1/sessions/{sess_id}/events")
    assert events_resp.status_code == 200
    events = events_resp.json()
    assert len(events) >= 2
    assert events[0]["seq"] == 1
    assert events[0]["event_type"] == "SESSION_CREATED"
    assert events[1]["seq"] == 2
    assert events[1]["event_type"] == "CHESS_MOVE"
    # Encadeamento criptográfico comprovado
    assert events[1]["prev_hash"] == events[0]["event_hash"]

    # 6. Execução de FUSION Research
    fusion_resp = client.post(f"/api/v1/sessions/{sess_id}/research/fusion", json={
        "strategies": ["queen", "king", "evans"]
    })
    assert fusion_resp.status_code == 200
    fusion_data = fusion_resp.json()
    assert len(fusion_data["branches"]) == 3
    assert "report" in fusion_data
    assert fusion_data["report"]["deduplicated_sources_count"] >= 1
    assert "unified_synthesis" in fusion_data["report"]

    # 7. Exportação de Relatório Markdown
    report_resp = client.get(f"/api/v1/sessions/{sess_id}/report", params={"format": "markdown"})
    assert report_resp.status_code == 200
    report_md = report_resp.text
    assert "Relatório de Auditoria e Investigação" in report_md
    assert sess_id in report_md
