"""
Gambit Lab 2.0 — Motores Determinísticos de Jogo
Xadrez 8x8 (com variante epistêmica) e Go 9x9 (regras completas de captura espacial e superko).
"""
from .chess_engine import EpistemicChessEngine, ChessMoveResult
from .go_engine import GoEngine9x9, GoMoveResult, GoStone

__all__ = [
    "EpistemicChessEngine",
    "ChessMoveResult",
    "GoEngine9x9",
    "GoMoveResult",
    "GoStone"
]
