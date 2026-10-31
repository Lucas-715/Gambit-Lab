"""
Unit tests for EpistemicChessEngine (RN-06, RN-07, RN-08, RF-10)
Inclui validação de casos extremos de xeque e IMPASSE_DA_VARIANTE (Problema 4).
"""
import pytest
from packages.game_rules.chess_engine import EpistemicChessEngine


def test_standard_chess_moves():
    engine = EpistemicChessEngine()
    assert engine.turn == "white"
    assert not engine.is_game_over

    res = engine.validate_and_apply_move("e2e4")
    assert res.legal
    assert not res.is_capture
    assert res.san == "e4"
    assert engine.turn == "black"

    res2 = engine.validate_and_apply_move("e7e5")
    assert res2.legal
    assert res2.san == "e5"
    assert engine.turn == "white"


def test_illegal_chess_move():
    engine = EpistemicChessEngine()
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

    res = engine.validate_and_apply_move(
        "e4d5",
        arbitration_verdict="INCONCLUSIVE",
        require_epistemic_capture=True
    )
    assert res.epistemic_blocked
    assert "REFUTED" in res.error
    assert engine.fen == fen_before


def test_epistemic_capture_gate_approved():
    """RN-06: Quando o veredito for REFUTED, a captura é consumada."""
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


def test_extreme_case_impasse_da_variante_when_only_escape_is_blocked_capture():
    """
    Problema 4: O que acontece se uma captura for necessária para escapar de um xeque,
    mas o árbitro considerar a evidência inconclusiva?
    Posição: Rei Branco em h1, Dama Preta em g2 sem proteção.
    A única jogada legal no Xadrez físico é h1xg2.
    Se a captura for bloqueada epistemologicamente, o sistema declara formalmente IMPASSE_DA_VARIANTE.
    """
    # FEN: 7k/8/8/8/8/8/6q1/7K w - - 0 1
    # White King on h1, Black Queen on g2, Black King on h8. Turn: White.
    fen_check = "7k/8/8/8/8/8/6q1/7K w - - 0 1"
    engine = EpistemicChessEngine(fen=fen_check)
    assert engine.board.is_check()

    # Verifica que h1xg2 é o único movimento legal em FIDE
    legal_moves = engine.get_legal_moves()
    assert legal_moves == ["h1g2"]

    # Tentativa de captura com evidência INCONCLUSIVA
    res = engine.validate_and_apply_move(
        "h1g2",
        arbitration_verdict="INCONCLUSIVE",
        require_epistemic_capture=True
    )

    assert res.is_impasse_variante
    assert res.epistemic_blocked
    assert engine.is_game_over
    assert engine.get_game_result() == "IMPASSE_DA_VARIANTE"
    assert "Xeque não resolvido" in res.diagnostic_reason


def test_ac21_castling_special_move():
    """AC-21: Validação de roque curto (O-O) e roque longo (O-O-O)."""
    # Monta posição onde o roque curto das brancas é legal
    # White: e1 (K), h1 (R); e2e4, g1f3, f1c4 jogados
    fen_castle = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
    engine = EpistemicChessEngine(fen=fen_castle)

    # Executa roque curto: e1g1
    res = engine.validate_and_apply_move("e1g1")
    assert res.legal
    assert not res.is_capture
    assert res.san == "O-O"
    assert "RNBQ1RK1" in engine.fen


def test_ac21_en_passant_with_epistemic_gate():
    """AC-21: Captura en passant com verificação de gate epistêmico."""
    # Posição: Peão branco em e5, Peão preto em d7 joga d7d5.
    fen_ep = "rnbqkbnr/pppppppp/8/4P3/8/8/PPPP1PPP/RNBQKBNR b KQkq - 0 2"
    engine = EpistemicChessEngine(fen=fen_ep)

    # Pretas jogam d7d5 (avanço de 2 casas adjacente a e5)
    res_d5 = engine.validate_and_apply_move("d7d5")
    assert res_d5.legal

    # Brancas têm captura en passant e5d6
    assert engine.is_capture_move("e5d6")

    # Tentativa com arbitragem recusada (INCONCLUSIVE)
    res_blocked = engine.validate_and_apply_move(
        "e5d6",
        arbitration_verdict="INCONCLUSIVE",
        require_epistemic_capture=True
    )
    assert res_blocked.epistemic_blocked

    # Tentativa com arbitragem aprovada (REFUTED)
    res_approved = engine.validate_and_apply_move(
        "e5d6",
        arbitration_verdict="REFUTED",
        require_epistemic_capture=True
    )
    assert res_approved.legal
    assert res_approved.is_capture
    assert res_approved.captured_piece == "p"


def test_ac21_pawn_promotion():
    """AC-21: Promoção de peão (ex: e7e8q)."""
    # Posição: Peão branco em e7 pronto para promover em e8
    fen_prom = "8/4P3/8/8/8/8/k7/7K w - - 0 1"
    engine = EpistemicChessEngine(fen=fen_prom)

    res = engine.validate_and_apply_move("e7e8q")
    assert res.legal
    assert res.san == "e8=Q"
    assert "Q" in engine.fen
