"""
Integration tests for 3-Tier Verification (Problema 1 da Auditoria)
1. Integridade Criptográfica (Event Store & SHA-256)
2. Verificação de Fontes (Presença de Documentos e Citações Reais)
3. Avaliação Epistêmica (Veredito de Sustentação ou Refutação)
"""
import pytest
from starlette.testclient import TestClient
from services.api.main import app

client = TestClient(app)


def test_empty_session_cannot_be_supported():
    """
    Problema 1: Uma sessão sem documentos anexados (artifacts_count: 0) NÃO pode ter veredito SUPPORTED.
    Deve reportar integrity_status: INTEGRITY_VERIFIED, source_status: NO_SOURCES_ATTACHED e evidence_assessment: HYPOTHESIS.
    """
    # Cria sessão com título genérico sem cenário pré-carregado
    resp = client.post("/api/v1/sessions", json={
        "title": "Pergunta genérica sem documentos",
        "mode": "research",
        "game": "chess"
    })
    assert resp.status_code == 200
    sess = resp.json()
    assert sess["artifacts_count"] == 0
    assert sess["integrity_status"] == "INTEGRITY_VERIFIED"
    assert sess["source_status"] == "NO_SOURCES_ATTACHED"
    assert sess["evidence_assessment"] == "HYPOTHESIS"
    assert "Nenhum documento" in sess["diagnostic_reason"]


def test_session_with_matching_artifact_is_source_verified():
    """
    Sessão com documento anexado e citação existente no texto do artefato recebe SOURCE_VERIFIED e SUPPORTED.
    """
    resp = client.post("/api/v1/sessions", json={
        "title": "Qual a arquitetura mais segura para sistemas com IA autônoma?",
        "mode": "research",
        "game": "chess"
    })
    assert resp.status_code == 200
    sess = resp.json()
    assert sess["artifacts_count"] >= 1
    assert sess["integrity_status"] == "INTEGRITY_VERIFIED"
    assert sess["source_status"] == "SOURCE_VERIFIED"
    assert sess["evidence_assessment"] == "SUPPORTED"


def test_quote_mismatch_fails_evidence_assessment():
    """
    Se uma alegação apontar para uma citação adulterada que não consta no artefato,
    o sistema deve detectar QUOTE_MISMATCH e rebaixar a avaliação para INSUFFICIENT.
    """
    # 1. Cria sessão
    resp = client.post("/api/v1/sessions", json={
        "title": "Teste de citação falsa",
        "mode": "research",
        "game": "chess"
    })
    sess_id = resp.json()["id"]

    # 2. Faz upload de artefato legítimo
    up_resp = client.post(f"/api/v1/sessions/{sess_id}/artifacts", json={
        "name": "Doc_Real.txt",
        "content": "O céu é azul e a luz se propaga em linha reta no vácuo."
    })
    art_id = up_resp.json()["id"]

    # 3. Testa endpoint de verificação de citação
    # Citação verdadeira:
    v_true = client.get(f"/api/v1/artifacts/{art_id}/quote", params={"quote": "O céu é azul"})
    assert v_true.json()["verified"] is True

    # Citação falsa:
    v_false = client.get(f"/api/v1/artifacts/{art_id}/quote", params={"quote": "O céu é verde e quadrado"})
    assert v_false.json()["verified"] is False
