"""
Unit tests for FusionOrchestrator (RF-20, RF-22, RF-23, RN-24, RN-25, AC-07, AC-08)
"""
import pytest
from services.api.fusion.pipeline import FusionOrchestrator


def test_fusion_multi_strategy_chess():
    """
    AC-07: FUSION dois gambitos isola tabuleiros e agrega fontes sem somar repetidas.
    """
    orchestrator = FusionOrchestrator()
    budget = {"max_calls": 15, "max_tokens": 50000, "current_calls": 0, "current_tokens": 0}
    artifacts = [{
        "id": "art_sample_01",
        "name": "Seguranca_Sistemas_IA.pdf",
        "sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        "content": "A conformidade técnica exige separação entre proposição e verificação."
    }]

    res = orchestrator.run_fusion_research(
        session_id="fusion_chess_01",
        question="Qual a melhor arquitetura de segurança para IA?",
        game="chess",
        strategy_keys=["queen", "king"],
        artifacts=artifacts,
        budget=budget
    )

    branches = res["branches"]
    assert len(branches) == 2
    assert branches[0]["preset"] == "queen"
    assert branches[1]["preset"] == "king"

    # Tabuleiros devem ser isolados e ter FENs válidos
    fen0 = branches[0]["board"]["fen"]
    fen1 = branches[1]["board"]["fen"]
    assert fen0 != fen1  # Aberturas distintas (Gambito da Dama d4/c4 vs Gambito do Rei e4/f4)

    # Relatório de síntese
    report = res["report"]
    assert report["deduplicated_sources_count"] == 1
    assert len(report["divergences"]) >= 1
    assert "Síntese Unificada FUSION" in report["unified_synthesis"]


def test_fusion_multi_strategy_go():
    """
    FUSION com lentes Go (influência e território).
    """
    orchestrator = FusionOrchestrator()
    budget = {"max_calls": 15, "max_tokens": 50000, "current_calls": 0, "current_tokens": 0}
    artifacts = [{
        "id": "art_go_01",
        "name": "Audit_Standards.pdf",
        "sha256": "9999991234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        "content": "Requisitos de auditoria contínua em inteligência artificial."
    }]

    res = orchestrator.run_fusion_research(
        session_id="fusion_go_01",
        question="Quais os principais riscos de conformidade em modelos generativos?",
        game="go",
        strategy_keys=["influence", "territory"],
        artifacts=artifacts,
        budget=budget
    )

    branches = res["branches"]
    assert len(branches) == 2
    assert branches[0]["preset"] == "influence"
    assert branches[1]["preset"] == "territory"

    # Pedras nos tabuleiros devem ser diferentes
    stones0 = [s["coord"] for s in branches[0]["board"]["stones"]]
    stones1 = [s["coord"] for s in branches[1]["board"]["stones"]]
    assert stones0 != stones1
