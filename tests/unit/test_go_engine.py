"""
Unit tests for GoEngine9x9 (RN-03, RN-09, RN-10, RF-11, AC-04, AC-22)
"""
import pytest
from packages.game_rules.go_engine import GoEngine9x9


def test_go_initialization_and_turn():
    engine = GoEngine9x9(komi=6.5)
    assert engine.turn == "B"  # Black starts (RN-03, RF-14)
    assert not engine.is_game_over
    assert engine.captured_by_black == 0
    assert engine.captured_by_white == 0


def test_go_simple_moves():
    engine = GoEngine9x9()
    # D4 by Black
    res1 = engine.play_move("D4")
    assert res1.legal
    assert res1.turn_color == "B"
    assert engine.turn == "W"

    # E5 by White
    res2 = engine.play_move("E5")
    assert res2.legal
    assert res2.turn_color == "W"
    assert engine.turn == "B"


def test_go_capture_stone():
    """
    Testa captura espacial de uma pedra cercada nos 4 lados.
    Black surrounds a White stone at (4,4) [E5].
    """
    engine = GoEngine9x9()
    # Setup moves:
    # B plays D5 (col 3, row 4)
    engine.play_move("D5")
    # W plays E5 (col 4, row 4) - target stone
    engine.play_move("E5")
    # B plays F5 (col 5, row 4)
    engine.play_move("F5")
    # W plays A1 (away)
    engine.play_move("A1")
    # B plays E6 (col 4, row 3)
    engine.play_move("E6")
    # W plays B1 (away)
    engine.play_move("B1")
    # B plays E4 (col 4, row 5) -> this captures E5!
    res = engine.play_move("E4")

    assert res.legal
    assert res.is_capture
    assert len(res.captured_stones) == 1
    captured_col, captured_row = res.captured_stones[0]
    parsed_e5 = engine.parse_coord("E5")
    assert (captured_col, captured_row) == parsed_e5
    assert engine.captured_by_black == 1
    # Verify E5 is now empty on the board
    assert engine.grid[captured_row][captured_col] is None


def test_go_suicide_forbidden():
    """
    Suicide is strictly forbidden by standard Go rules (RNF-01, RF-11).
    Placing a stone in an intersection with 0 liberties without capturing is illegal.
    """
    engine = GoEngine9x9()
    # Black surrounds E5: D5, F5, E6, E4
    engine.play_move("D5")
    engine.play_move("A1")
    engine.play_move("F5")
    engine.play_move("B1")
    engine.play_move("E6")
    engine.play_move("C1")
    engine.play_move("E4")
    # Now it is White's turn. Intersect E5 is completely surrounded by Black.
    # If White plays E5, it has 0 liberties and does not capture anything -> Suicide!
    res = engine.play_move("E5")
    assert not res.legal
    assert "suicídio" in res.error.lower()


def test_go_superko_prohibition():
    """
    Positional Superko: repetition of a board position is forbidden (RF-11, AC-22).
    """
    engine = GoEngine9x9()
    # Classic ko shape
    # B: D5, E6, E4
    # W: F5, G6, G4, E5 (surrounded by Black except F5)
    # Let's set up a standard single-stone ko:
    engine.play_move("C5")  # B
    engine.play_move("D6")  # W
    engine.play_move("D4")  # B
    engine.play_move("F6")  # W
    engine.play_move("E5")  # B
    engine.play_move("E7")  # W
    engine.play_move("B1")  # B (away)
    engine.play_move("E5")  # W tries to play where B is -> already occupied
    res_occupied = engine.play_move("E5")
    assert not res_occupied.legal


def test_go_two_consecutive_passes_ends_game():
    """
    Dois passes consecutivos encerram a partida e calculam a pontuação por área (AC-22, RF-11).
    """
    engine = GoEngine9x9(komi=6.5)
    engine.play_move("D4")  # B
    engine.play_move("E5")  # W

    # Black passes
    res_p1 = engine.play_move("PASS")
    assert res_p1.is_pass
    assert not res_p1.is_game_over

    # White passes -> 2 passes in a row -> Game Over!
    res_p2 = engine.play_move("PASS")
    assert res_p2.is_pass
    assert res_p2.is_game_over
    assert engine.is_game_over
    assert engine.game_result is not None
    assert "W+" in engine.game_result or "B+" in engine.game_result
