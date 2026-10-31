"""
Unit tests for EpistemicChessEngine (RN-06, RN-07, RN-08, RF-10)
"""
import pytest
from packages.game_rules.chess_engine import EpistemicChessEngine


def test_standard_chess_moves():
    engine = EpistemicChessEngine()
    assert engine.turn == "white"
    assert not engine.is_game_over

    # Normal move e2e4
    res = engine.validate_and_apply_move("e2e4")
    assert res.legal
    assert not res.is_capture
    assert res.san == "e4"
    assert engine.turn == "black"

    # Black responds e7e5
    res2 = engine.validate_and_apply_move("e7e5")
    assert res2.legal
    assert res2.san == "e5"
    assert engine.turn == "white"


def test_illegal_chess_move():
    engine = EpistemicChessEngine()
    # Pawn cannot jump diagonally without capture
    res = engine.validate_and_apply_move("e2d3")
    assert not res.legal
    assert "ilegal" in res.error.lower()


def test_epistemic_capture_gate_refused():
    """
    RN-06: No Xadrez com captura condicionada, a captura exige veredito REFUTED da alegação alvo.
    Se não houver veredito ou for INCONCLUSIVE, a captura é bloqueada e o estado permanece inalterado.
    """
    engine = EpistemicChessEngine()
    engine.validate_and_apply_move("e2e4")
    engine.validate_and_apply_move("d7d5")

    fen_before = engine.fen

    # e4xd5 is a legal capture on the board, but epistemic capture requires REFUTED
    res = engine.validate_and_apply_move(
        "e4d5",
        arbitration_verdict="INCONCLUSIVE",
        require_epistemic_capture=True
    )
    assert res.epistemic_blocked
    assert "REFUTED" in res.error
    # Board state must NOT change
    assert engine.fen == fen_before


def test_epistemic_capture_gate_approved():
    """
    RN-06: Quando o veredito for REFUTED, a captura é consumada.
    """
    engine = EpistemicChessEngine()
    engine.validate_and_apply_move("e2e4")
    engine.validate_and_apply_move("d7d5")

    fen_before = engine.fen

    res = engine.validate_and_apply_move(
        "e4d5",
        arbitration_verdict="REFUTED",
        require_epistemic_capture=True
    )
    assert res.legal
    assert res.is_capture
    assert not res.epistemic_blocked
    assert engine.fen != fen_before
    assert res.captured_piece == "p"


def test_scholars_mate():
    """Verifica detecção formal de xeque-mate."""
    engine = EpistemicChessEngine()
    engine.validate_and_apply_move("e2e4")
    engine.validate_and_apply_move("e7e5")
    engine.validate_and_apply_move("d1h5")
    engine.validate_and_apply_move("b8c6")
    engine.validate_and_apply_move("f1c4")
    engine.validate_and_apply_move("g8f6")
    res = engine.validate_and_apply_move("h5f7")

    assert res.is_checkmate
    assert engine.is_game_over
    assert engine.get_game_result() == "1-0"
