"""
Deterministic 9x9 Go Engine — Gambit Lab 2.0
Implementação pura e determinística das regras oficiais de Go/Weiqi em 9x9:
liberdades, grupos, captura automática por cerco, proibição de suicídio,
superko posicional, passes consecutivos e contagem por área com komi (RN-03, RN-09, RF-11).
"""
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Set, Dict, Any
import copy

COLS_STR = "ABCDEFGHJ"  # Go convention: omits 'I' to avoid confusion with '1' or 'J'

@dataclass
class GoStone:
    col: int  # 0 to 8
    row: int  # 0 to 8
    color: str  # 'B' (Black) or 'W' (White)


@dataclass
class GoMoveResult:
    legal: bool
    is_pass: bool = False
    is_capture: bool = False
    captured_stones: List[Tuple[int, int]] = field(default_factory=list)
    coord_str: str = ""
    turn_color: str = ""
    is_game_over: bool = False
    game_result: Optional[str] = None
    black_score: float = 0.0
    white_score: float = 0.0
    error: Optional[str] = None


class GoEngine9x9:
    """
    Motor determinístico de Go 9x9 com conformidade total às invariantes de domínio.
    """

    def __init__(self, komi: float = 6.5):
        self.size = 9
        self.komi = komi
        # Grid: 9x9 list of Optional[str]: None, 'B', or 'W'
        self.grid: List[List[Optional[str]]] = [[None for _ in range(9)] for _ in range(9)]
        self.turn: str = "B"  # Pretas começam (RN-03)
        self.consecutive_passes: int = 0
        self.is_game_over: bool = False
        self.game_result: Optional[str] = None
        self.captured_by_black: int = 0
        self.captured_by_white: int = 0
        self.move_history: List[Dict[str, Any]] = []
        # Histórico de posições para detecção de superko posicional
        self.position_history: Set[str] = {self._board_hash(self.grid)}

    @staticmethod
    def _board_hash(grid: List[List[Optional[str]]]) -> str:
        return "".join((cell if cell else ".") for row in grid for cell in row)

    @classmethod
    def parse_coord(cls, coord: str) -> Optional[Tuple[int, int]]:
        """Converte strings como 'D4', 'd4', 'e5' ou '4,4' em (col, row)."""
        coord = coord.strip().upper()
        if coord == "PASS":
            return None
        if "," in coord:
            parts = coord.split(",")
            if len(parts) == 2:
                try:
                    return int(parts[0]), int(parts[1])
                except ValueError:
                    return None
        if len(coord) >= 2:
            col_char = coord[0]
            row_str = coord[1:]
            if col_char in COLS_STR:
                c = COLS_STR.index(col_char)
            elif 'A' <= col_char <= 'I':
                c = ord(col_char) - ord('A')
            else:
                return None
            try:
                # Na notação padrão Go, linha 1 é o fundo (row=8) ou topo (row=0).
                # Padronizamos 1 = fundo (row 8), 9 = topo (row 0)
                r_num = int(row_str)
                if 1 <= r_num <= 9:
                    r = 9 - r_num
                    return c, r
            except ValueError:
                return None
        return None

    @classmethod
    def format_coord(cls, col: int, row: int) -> str:
        col_char = COLS_STR[col] if 0 <= col < len(COLS_STR) else "?"
        row_num = 9 - row
        return f"{col_char}{row_num}"

    def get_neighbors(self, c: int, r: int) -> List[Tuple[int, int]]:
        neighbors = []
        for dc, dr in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nc, nr = c + dc, r + dr
            if 0 <= nc < self.size and 0 <= nr < self.size:
                neighbors.append((nc, nr))
        return neighbors

    def get_group(self, c: int, r: int, grid: List[List[Optional[str]]]) -> Tuple[Set[Tuple[int, int]], Set[Tuple[int, int]]]:
        """
        Retorna (pedras_do_grupo, liberdades_do_grupo).
        """
        color = grid[r][c]
        if color is None:
            return set(), set()

        group_stones: Set[Tuple[int, int]] = set()
        liberties: Set[Tuple[int, int]] = set()
        queue = [(c, r)]
        visited = set()

        while queue:
            curr_c, curr_r = queue.pop(0)
            if (curr_c, curr_r) in visited:
                continue
            visited.add((curr_c, curr_r))
            group_stones.add((curr_c, curr_r))

            for nc, nr in self.get_neighbors(curr_c, curr_r):
                neighbor_color = grid[nr][nc]
                if neighbor_color is None:
                    liberties.add((nc, nr))
                elif neighbor_color == color and (nc, nr) not in visited:
                    queue.append((nc, nr))

        return group_stones, liberties

    def is_legal_move(self, col: int, row: int, color: Optional[str] = None) -> Tuple[bool, Optional[str], List[Tuple[int, int]]]:
        """
        Valida se um lance é legal:
        - Dentro do tabuleiro
        - Interseção vazia
        - Captura grupos adversários com 0 liberdades
        - Sem suicídio
        - Respeita Superko Posicional
        """
        if self.is_game_over:
            return False, "O jogo já foi finalizado.", []

        if not (0 <= col < self.size and 0 <= row < self.size):
            return False, f"Coordenada ({col}, {row}) fora do tabuleiro 9x9.", []

        if self.grid[row][col] is not None:
            return False, f"Interseção ({col}, {row}) já ocupada.", []

        acting_color = color or self.turn
        opponent_color = "W" if acting_color == "B" else "B"

        # Simula o lance em cópia do tabuleiro
        sim_grid = [row_cells.copy() for row_cells in self.grid]
        sim_grid[row][col] = acting_color

        # Verifica e remove grupos adversários cercados (capturas)
        captured: List[Tuple[int, int]] = []
        for nc, nr in self.get_neighbors(col, row):
            if sim_grid[nr][nc] == opponent_color:
                group, liberties = self.get_group(nc, nr, sim_grid)
                if len(liberties) == 0:
                    for sc, sr in group:
                        if (sc, sr) not in captured:
                            captured.append((sc, sr))

        for sc, sr in captured:
            sim_grid[sr][sc] = None

        # Verifica se o próprio grupo tem liberdades (proibição de suicídio)
        my_group, my_liberties = self.get_group(col, row, sim_grid)
        if len(my_liberties) == 0:
            return False, "Suicídio é proibido pelas regras de Go.", []

        # Verifica Superko Posicional (não repetir posição anterior do jogo)
        sim_hash = self._board_hash(sim_grid)
        if sim_hash in self.position_history:
            return False, "Violação de Superko: repetição de posição anterior no tabuleiro.", []

        return True, None, captured

    def play_move(self, coord_str: str) -> GoMoveResult:
        """
        Executa uma jogada (ou passe).
        """
        acting_color = self.turn
        if coord_str.strip().upper() == "PASS":
            return self.pass_turn()

        parsed = self.parse_coord(coord_str)
        if parsed is None:
            return GoMoveResult(
                legal=False,
                coord_str=coord_str,
                turn_color=acting_color,
                error=f"Coordenada inválida: {coord_str}"
            )

        col, row = parsed
        is_legal, error, captured = self.is_legal_move(col, row, acting_color)
        if not is_legal:
            return GoMoveResult(
                legal=False,
                coord_str=coord_str,
                turn_color=acting_color,
                error=error
            )

        # Aplica a jogada
        self.grid[row][col] = acting_color
        for sc, sr in captured:
            self.grid[sr][sc] = None

        if acting_color == "B":
            self.captured_by_black += len(captured)
        else:
            self.captured_by_white += len(captured)

        # Atualiza histórico de posições
        self.position_history.add(self._board_hash(self.grid))
        self.consecutive_passes = 0

        self.move_history.append({
            "col": col,
            "row": row,
            "coord": self.format_coord(col, row),
            "color": acting_color,
            "captured_count": len(captured),
            "captured": captured
        })

        # Alterna o turno
        self.turn = "W" if acting_color == "B" else "B"

        return GoMoveResult(
            legal=True,
            is_pass=False,
            is_capture=len(captured) > 0,
            captured_stones=captured,
            coord_str=self.format_coord(col, row),
            turn_color=acting_color
        )

    def pass_turn(self) -> GoMoveResult:
        """Executa um passe voluntário. Dois passes consecutivos encerram a partida."""
        acting_color = self.turn
        self.consecutive_passes += 1
        self.move_history.append({
            "col": -1,
            "row": -1,
            "coord": "PASS",
            "color": acting_color,
            "captured_count": 0,
            "captured": []
        })

        if self.consecutive_passes >= 2:
            self.is_game_over = True
            b_score, w_score = self.calculate_area_score()
            if b_score > w_score:
                self.game_result = f"B+{round(b_score - w_score, 1)}"
            else:
                self.game_result = f"W+{round(w_score - b_score, 1)}"

            return GoMoveResult(
                legal=True,
                is_pass=True,
                coord_str="PASS",
                turn_color=acting_color,
                is_game_over=True,
                game_result=self.game_result,
                black_score=b_score,
                white_score=w_score
            )

        self.turn = "W" if acting_color == "B" else "B"
        return GoMoveResult(
            legal=True,
            is_pass=True,
            coord_str="PASS",
            turn_color=acting_color
        )

    def resign(self, color: str) -> GoMoveResult:
        self.is_game_over = True
        winner = "W" if color.upper().startswith("B") else "B"
        self.game_result = f"{winner}+R"
        return GoMoveResult(
            legal=True,
            is_game_over=True,
            game_result=self.game_result,
            turn_color=color
        )

    def calculate_area_score(self) -> Tuple[float, float]:
        """
        Cálculo de pontuação por área (regras chinesas):
        Pontos Pretas = Pedras pretas vivas + Interseções vazias cercadas exclusivamente por pretas.
        Pontos Brancas = Pedras brancas vivas + Interseções vazias cercadas exclusivamente por brancas + komi.
        """
        black_stones = sum(row.count("B") for row in self.grid)
        white_stones = sum(row.count("W") for row in self.grid)

        # Encontra territórios cercados
        visited_empty = set()
        black_territory = 0
        white_territory = 0

        for r in range(self.size):
            for c in range(self.size):
                if self.grid[r][c] is None and (c, r) not in visited_empty:
                    # BFS para mapear região vazia e checar fronteiras
                    region = []
                    borders: Set[str] = set()
                    q = [(c, r)]
                    reg_visited = set()

                    while q:
                        curr_c, curr_r = q.pop(0)
                        if (curr_c, curr_r) in reg_visited:
                            continue
                        reg_visited.add((curr_c, curr_r))
                        region.append((curr_c, curr_r))

                        for nc, nr in self.get_neighbors(curr_c, curr_r):
                            cell_val = self.grid[nr][nc]
                            if cell_val is None:
                                if (nc, nr) not in reg_visited:
                                    q.append((nc, nr))
                            else:
                                borders.add(cell_val)

                    visited_empty.update(reg_visited)

                    # Se a região faz fronteira exclusivamente com uma cor, é território
                    if borders == {"B"}:
                        black_territory += len(region)
                    elif borders == {"W"}:
                        white_territory += len(region)

        total_black = float(black_stones + black_territory)
        total_white = float(white_stones + white_territory) + self.komi

        return total_black, total_white

    def to_dict(self) -> Dict[str, Any]:
        stones = []
        for r in range(self.size):
            for c in range(self.size):
                if self.grid[r][c]:
                    stones.append({
                        "col": c,
                        "row": r,
                        "coord": self.format_coord(c, r),
                        "color": self.grid[r][c]
                    })
        return {
            "game": "go",
            "size": self.size,
            "turn": "black" if self.turn == "B" else "white",
            "komi": self.komi,
            "stones": stones,
            "captured_by_black": self.captured_by_black,
            "captured_by_white": self.captured_by_white,
            "is_game_over": self.is_game_over,
            "game_result": self.game_result,
            "consecutive_passes": self.consecutive_passes
        }

