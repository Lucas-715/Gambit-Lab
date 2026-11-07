"""
Jogador determinístico de Xadrez para o Research Match.

Busca negamax com poda alfa-beta (profundidade 2 + quiescência de capturas) sobre `python-chess`.
- 100% determinístico: variação entre sessões vem de uma semente derivada do id da sessão (sha256),
  nunca de `hash()` do Python (randomizado por processo) — requisito do replay auditável.
- Não chama LLM: o LLM propõe teses e evidências; os lances são escolhidos aqui e validados pelo motor.
"""
import hashlib
from typing import Dict, List, Optional, Tuple

import chess

PIECE_VALUES_CP: Dict[int, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}
MATE_SCORE = 100_000


def material_cp(board: chess.Board, color: chess.Color) -> int:
    """Material (centipeões) de uma cor, sem o rei."""
    return sum(
        len(board.pieces(pt, color)) * val for pt, val in PIECE_VALUES_CP.items() if pt != chess.KING
    )


def material_diff_white_cp(board: chess.Board) -> int:
    return material_cp(board, chess.WHITE) - material_cp(board, chess.BLACK)


def _centrality(square: int) -> float:
    f, r = chess.square_file(square), chess.square_rank(square)
    return 3.5 - (abs(f - 3.5) + abs(r - 3.5)) / 2.0


class ChessPlayer:
    def __init__(self, seed: str, depth: int = 2, max_nodes_per_candidate: int = 128):
        self.seed = seed
        self.depth = depth
        self.max_nodes_per_candidate = max(1, max_nodes_per_candidate)
        self._nodes = 0

    def _noise(self, key: str) -> float:
        """Perturbação determinística em [-6, +6] centipeões (desempate reprodutível)."""
        digest = hashlib.sha256(f"{self.seed}|{key}".encode("utf-8")).digest()
        return (digest[0] / 255.0 - 0.5) * 12.0

    def evaluate_white(self, board: chess.Board) -> float:
        """Avaliação estática do ponto de vista das Brancas."""
        score = 0.0
        for sq, piece in board.piece_map().items():
            val = PIECE_VALUES_CP[piece.piece_type]
            pos = 0.0
            if piece.piece_type in (chess.KNIGHT, chess.BISHOP):
                pos = _centrality(sq) * 9.0
            elif piece.piece_type == chess.PAWN:
                adv = chess.square_rank(sq) if piece.color == chess.WHITE else 7 - chess.square_rank(sq)
                pos = adv * 6.0 + _centrality(sq) * 2.0
            elif piece.piece_type == chess.QUEEN:
                pos = _centrality(sq) * 2.0
            elif piece.piece_type == chess.KING:
                pos = -_centrality(sq) * 4.0  # rei prefere cantos no meio-jogo
            total = val + pos
            score += total if piece.color == chess.WHITE else -total
        return score

    def _eval_for_side_to_move(self, board: chess.Board) -> float:
        e = self.evaluate_white(board)
        return e if board.turn == chess.WHITE else -e

    @staticmethod
    def _order(board: chess.Board, moves: List[chess.Move]) -> List[chess.Move]:
        def key(m: chess.Move):
            victim = board.piece_at(m.to_square)
            cap = PIECE_VALUES_CP[victim.piece_type] if victim else (100 if board.is_en_passant(m) else 0)
            att = board.piece_at(m.from_square)
            att_v = PIECE_VALUES_CP[att.piece_type] if att else 0
            return (-(cap * 10 - att_v), m.uci())
        return sorted(moves, key=key)

    def _quiesce(self, board: chess.Board, alpha: float, beta: float, qdepth: int) -> float:
        self._nodes += 1
        stand = self._eval_for_side_to_move(board)
        if qdepth <= 0 or self._nodes >= self.max_nodes_per_candidate:
            return stand
        if stand >= beta:
            return stand
        alpha = max(alpha, stand)
        caps = [m for m in board.legal_moves if board.is_capture(m)]
        for m in self._order(board, caps):
            board.push(m)
            score = -self._quiesce(board, -beta, -alpha, qdepth - 1)
            board.pop()
            if score >= beta:
                return score
            alpha = max(alpha, score)
            if self._nodes >= self.max_nodes_per_candidate:
                break
        return alpha

    def _negamax(self, board: chess.Board, depth: int, alpha: float, beta: float, ply: int) -> float:
        self._nodes += 1
        if board.is_checkmate():
            return -MATE_SCORE + ply
        if board.is_stalemate() or board.is_insufficient_material():
            return 0.0
        if self._nodes >= self.max_nodes_per_candidate:
            return self._eval_for_side_to_move(board)
        if depth <= 0:
            return self._quiesce(board, alpha, beta, 3)
        best = -float("inf")
        for m in self._order(board, list(board.legal_moves)):
            board.push(m)
            score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            board.pop()
            if score > best:
                best = score
            alpha = max(alpha, score)
            if alpha >= beta or self._nodes >= self.max_nodes_per_candidate:
                break
        return best

    def rank_moves(
        self, board: chess.Board, bias_by_square: Optional[Dict[int, float]] = None
    ) -> List[Tuple[float, chess.Move]]:
        """Ranqueia lances legais (melhor primeiro). `bias_by_square` soma um viés (cp) ao lance da peça naquela casa."""
        bias_by_square = bias_by_square or {}
        ranked: List[Tuple[float, chess.Move]] = []
        for m in self._order(board, list(board.legal_moves)):
            self._nodes = 0
            board.push(m)
            if board.is_checkmate():
                score = float(MATE_SCORE)
            else:
                score = -self._negamax(board, self.depth - 1, -float("inf"), float("inf"), 1)
                if board.is_repetition(2):
                    score -= 60.0  # evita estagnação por repetição
            board.pop()
            score += bias_by_square.get(m.from_square, 0.0) + self._noise(f"{board.fen()}|{m.uci()}")
            ranked.append((score, m))
        ranked.sort(key=lambda x: (-x[0], x[1].uci()))
        return ranked

