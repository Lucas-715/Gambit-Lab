"""
Epistemic Chess Engine — Gambit Lab 2.0
Baseado em python-chess com suporte a variantes epistêmicas,
arbitragem de capturas condicionadas e formalização de IMPASSE_DA_VARIANTE em xeques.
(RN-06, RN-07, RN-08, RF-10, RF-15, RF-17)
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import chess


@dataclass
class ChessMoveResult:
    legal: bool
    is_capture: bool
    san: str = ""
    uci: str = ""
    fen_after: str = ""
    is_check: bool = False
    is_checkmate: bool = False
    is_stalemate: bool = False
    is_draw: bool = False
    is_impasse_variante: bool = False
    epistemic_blocked: bool = False
    error: Optional[str] = None
    captured_piece: Optional[str] = None
    diagnostic_code: Optional[str] = None
    diagnostic_reason: Optional[str] = None


class EpistemicChessEngine:
    """
    Controlador determinístico de Xadrez com regras oficiais FIDE e suporte
    à variante epistêmica de captura condicionada (RN-06, RN-07, RN-08).
    """

    def __init__(self, fen: Optional[str] = None):
        self.board = chess.Board(fen) if fen else chess.Board()
        self.move_history: List[Dict[str, Any]] = []
        self._impasse_declared = False
        self._impasse_diagnostic: Optional[str] = None

    @property
    def fen(self) -> str:
        return self.board.fen()

    @property
    def turn(self) -> str:
        return "white" if self.board.turn == chess.WHITE else "black"

    @property
    def fullmove_number(self) -> int:
        return self.board.fullmove_number

    @property
    def ply_count(self) -> int:
        return len(self.move_history)

    @property
    def is_game_over(self) -> bool:
        if self._impasse_declared:
            return True
        return self.board.is_game_over()

    def get_game_result(self) -> Optional[str]:
        if self._impasse_declared:
            return "IMPASSE_DA_VARIANTE"
        if not self.board.is_game_over():
            return None
        outcome = self.board.outcome()
        if outcome is None:
            return None
        if outcome.winner == chess.WHITE:
            return "1-0"
        elif outcome.winner == chess.BLACK:
            return "0-1"
        else:
            return "1/2-1/2"

    def is_capture_move(self, move_uci: str) -> bool:
        try:
            move = chess.Move.from_uci(move_uci)
            return self.board.is_capture(move)
        except Exception:
            return False

    def get_legal_moves(self) -> List[str]:
        return [move.uci() for move in self.board.legal_moves]

    def validate_and_apply_move(
        self,
        move_uci: str,
        arbitration_verdict: Optional[str] = None,
        require_epistemic_capture: bool = False
    ) -> ChessMoveResult:
        """
        Valida e executa o lance.
        - Lances não capturantes seguem as regras normais sem refutação.
        - Se require_epistemic_capture for True e o lance for uma captura:
          A captura só é aplicada se arbitration_verdict == 'REFUTED'.
        - Casos Extremos (Problema 4): Se a captura for necessária para escapar de um xeque
          e o veredito não for REFUTED:
          1. Se existirem outros lances legais não-capturantes, rejeita a jogada e indica alternativa.
          2. Se a ÚNICA saída física for a captura bloqueada, formaliza IMPASSE_DA_VARIANTE.
        """
        if self._impasse_declared:
            return ChessMoveResult(
                legal=False,
                is_capture=False,
                is_impasse_variante=True,
                error="Partida finalizada por IMPASSE_DA_VARIANTE.",
                diagnostic_reason=self._impasse_diagnostic
            )

        try:
            move = chess.Move.from_uci(move_uci)
        except ValueError:
            return ChessMoveResult(
                legal=False,
                is_capture=False,
                error=f"Formato de movimento UCI inválido: {move_uci}"
            )

        if move not in self.board.legal_moves:
            return ChessMoveResult(
                legal=False,
                is_capture=False,
                error=f"Lance ilegal para a posição atual: {move_uci}"
            )

        is_capture = self.board.is_capture(move)
        in_check_before = self.board.is_check()

        # Verificação epistêmica da variante para capturas (RN-06)
        if require_epistemic_capture and is_capture:
            if arbitration_verdict != "REFUTED":
                # Avalia saídas alternativas quando sob xeque
                all_legal = list(self.board.legal_moves)
                non_capturing = [m for m in all_legal if not self.board.is_capture(m)]

                if in_check_before and len(non_capturing) == 0:
                    # CASO EXTREMO: A única saída física de xeque é uma captura epistemologicamente bloqueada!
                    self._impasse_declared = True
                    self._impasse_diagnostic = (
                        "Xeque não resolvido: a única saída física no tabuleiro requer uma captura "
                        "bloqueada por falta de refutação factual da alegação adversária (IMPASSE_DA_VARIANTE)."
                    )
                    return ChessMoveResult(
                        legal=True,
                        is_capture=True,
                        uci=move_uci,
                        fen_after=self.board.fen(),
                        is_check=True,
                        is_impasse_variante=True,
                        epistemic_blocked=True,
                        error="IMPASSE_DA_VARIANTE: O rei não possui movimentos não-capturantes legais e a captura da peça atacante foi rejeitada pelo árbitro.",
                        diagnostic_code="IMPASSE_DA_VARIANTE",
                        diagnostic_reason=self._impasse_diagnostic
                    )
                else:
                    alt_msg = " Existem lances alternativos legais sem captura para escapar do xeque." if in_check_before else ""
                    return ChessMoveResult(
                        legal=True,
                        is_capture=True,
                        uci=move_uci,
                        fen_after=self.board.fen(),
                        is_check=in_check_before,
                        epistemic_blocked=True,
                        error=f"Captura rejeitada: a alegação alvo requer veredito REFUTED pelo árbitro (recebido: {arbitration_verdict}).{alt_msg}",
                        diagnostic_code="ALTERNATIVE_ESCAPE_AVAILABLE" if in_check_before else "REFUTATION_REQUIRED",
                        diagnostic_reason="A alegação defensiva do alvo não foi refutada com evidência suficiente."
                    )

        san = self.board.san(move)
        captured_piece_sym = None
        if is_capture:
            target_sq = move.to_square
            piece = self.board.piece_at(target_sq)
            if piece:
                captured_piece_sym = piece.symbol()
            elif self.board.is_en_passant(move):
                captured_piece_sym = "p" if self.board.turn == chess.WHITE else "P"

        self.board.push(move)

        fen_after = self.board.fen()
        is_check = self.board.is_check()
        is_checkmate = self.board.is_checkmate()
        is_stalemate = self.board.is_stalemate()
        is_draw = self.board.is_insufficient_material() or self.board.can_claim_draw()

        self.move_history.append({
            "uci": move_uci,
            "san": san,
            "turn": "white" if self.board.turn == chess.BLACK else "black",
            "fen": fen_after,
            "is_capture": is_capture,
            "captured_piece": captured_piece_sym
        })

        return ChessMoveResult(
            legal=True,
            is_capture=is_capture,
            san=san,
            uci=move_uci,
            fen_after=fen_after,
            is_check=is_check,
            is_checkmate=is_checkmate,
            is_stalemate=is_stalemate,
            is_draw=is_draw,
            captured_piece=captured_piece_sym
        )

    def to_dict(self) -> Dict[str, Any]:
        last_move = self.move_history[-1]["uci"] if self.move_history else None
        return {
            "game": "chess",
            "fen": self.fen,
            "turn": self.turn,
            "fullmove": self.fullmove_number,
            "ply_count": self.ply_count,
            "last_move": last_move,
            "is_check": self.board.is_check(),
            "is_game_over": self.is_game_over,
            "game_result": self.get_game_result(),
            "is_impasse_variante": self._impasse_declared,
            "diagnostic_reason": self._impasse_diagnostic,
            "legal_moves": self.get_legal_moves()[:20]
        }
