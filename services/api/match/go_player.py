"""
Jogador determinístico de Go 9x9 para o Research Match.

Heurística tática simples e reprodutível (sem LLM): capturas, atari, salvamento de grupos,
abertura em pontos estratégicos e proibição de preencher os próprios olhos.
O jogador PASSA quando não resta jogada útil — é isso que encerra a partida naturalmente
(dois passes consecutivos → pontuação por área com komi), sem número fixo de jogadas.
"""
import hashlib
from typing import Dict, List, Optional, Tuple

from packages.game_rules.go_engine import GoEngine9x9

OPENING_POINTS = ["E5", "C3", "G7", "C7", "G3", "D4", "F6", "F4", "D6"]


class GoPlayer:
    def __init__(self, seed: str):
        self.seed = seed

    def _noise(self, key: str) -> float:
        digest = hashlib.sha256(f"{self.seed}|{key}".encode("utf-8")).digest()
        return digest[0] / 255.0 * 0.3

    def _score_point(self, engine: GoEngine9x9, c: int, r: int, captured: List[Tuple[int, int]], ply: int) -> Optional[float]:
        me = engine.turn
        opp = "W" if me == "B" else "B"
        neighbors = engine.get_neighbors(c, r)
        own_adj = sum(1 for nc, nr in neighbors if engine.grid[nr][nc] == me)
        empty_adj = sum(1 for nc, nr in neighbors if engine.grid[nr][nc] is None)

        # Não preencher o próprio olho (todos os vizinhos são pedras próprias) sem capturar nada.
        if not captured and neighbors and own_adj == len(neighbors):
            return None

        score = 0.0
        if captured:
            score += 10.0 + 2.0 * len(captured)

        saves = False
        for nc, nr in neighbors:
            cell = engine.grid[nr][nc]
            if cell == opp:
                _, libs = engine.get_group(nc, nr, engine.grid)
                if len(libs) == 2:
                    score += 3.0  # atari
            elif cell == me:
                _, libs = engine.get_group(nc, nr, engine.grid)
                if len(libs) == 1:
                    saves = True
        if saves:
            score += 6.0

        # Autoatari: grupo resultante com 1 liberdade e sem captura.
        sim = [row.copy() for row in engine.grid]
        sim[r][c] = me
        for sc, sr in captured:
            sim[sr][sc] = None
        _, my_libs = engine.get_group(c, r, sim)
        if not captured and len(my_libs) == 1:
            score -= 8.0

        coord = engine.format_coord(c, r)
        if ply <= 12 and coord in OPENING_POINTS:
            score += 4.0 - OPENING_POINTS.index(coord) * 0.25

        tactical = bool(captured) or saves or score >= 3.0
        # Jogada de expansão só vale se ainda houver espaço (>= 2 liberdades vazias adjacentes);
        # isso faz as fronteiras se fecharem e o jogo terminar por passes.
        if not tactical and empty_adj < 2:
            return None

        centrality = 4 - (abs(c - 4) + abs(r - 4)) / 2.0
        score += 0.35 * centrality + 0.55 * own_adj + 0.2 * empty_adj
        score += self._noise(f"{ply}|{coord}")
        return score

    def choose(self, engine: GoEngine9x9, ply: int) -> str:
        best: Optional[Tuple[float, str]] = None
        for r in range(engine.size):
            for c in range(engine.size):
                if engine.grid[r][c] is not None:
                    continue
                ok, _, captured = engine.is_legal_move(c, r, engine.turn)
                if not ok:
                    continue
                sc = self._score_point(engine, c, r, captured, ply)
                if sc is None:
                    continue
                coord = engine.format_coord(c, r)
                if best is None or sc > best[0] or (sc == best[0] and coord < best[1]):
                    best = (sc, coord)
        if best is None or best[0] < 0.9:
            return "PASS"
        return best[1]

    @staticmethod
    def nearest_group_id(coord: str, groups: List[Dict], engine: GoEngine9x9) -> str:
        """Atribui a pedra ao bloco argumentativo (grupo-papel) de âncora mais próxima."""
        parsed = engine.parse_coord(coord)
        if parsed is None:
            return groups[0]["piece_id"]
        c, r = parsed

        def dist(g: Dict) -> int:
            ap = engine.parse_coord(g["initial_coord"])
            return abs(ap[0] - c) + abs(ap[1] - r) if ap else 99

        return min(groups, key=lambda g: (dist(g), g["piece_id"]))["piece_id"]

