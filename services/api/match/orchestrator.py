"""
Research Match — controlador do ciclo de vida (v2.2).

Responsabilidades (cada uma em seu módulo):
  orchestrator.py  → ciclo de vida: estágios 1..7, retomada, redação por visão do lado   (este arquivo)
  preparation.py   → estágios 1, 2 e 4: lados, pesquisa isolada por cofre, dossiês por peça
  play.py          → estágio 5: partida completa e retomável nos motores determinísticos
  chess_player.py / go_player.py → escolha de lances (sem LLM, determinística)
  conclusion.py    → estágios 6 e 7: duplo resultado, ponto de virada, síntese, selagem do replay
  recording.py     → eventos canônicos (CHESS_MOVE/GO_MOVE, claims, julgamentos) para o replay

Pipeline de 7 estágios (cada um é uma chamada curta e REINICIÁVEL; falha de provedor não perde o que já foi feito):
  1 BUILD_SIDES · 2 RESEARCH_PRO · 3 RESEARCH_CONTRA · 4 ASSIGN_PIECES · 5 GENERATE_MATCH · 6 EVALUATE_WINNER · 7 BUILD_REPLAY
"""
import copy
import datetime
from typing import Any, Dict, List, Optional

from services.api.match.conclusion import ConclusionMixin
from services.api.match.play import PlayMixin
from services.api.match.preparation import PreparationMixin
from services.api.match.recording import RecordingMixin
from services.api.models.schemas import MatchStageInfoSchema, ResearchMatchStateSchema

STAGE_DEFINITIONS = [
    (1, "BUILD_SIDES", "Construindo lados"),
    (2, "RESEARCH_PRO", "Pesquisando argumentos favoráveis"),
    (3, "RESEARCH_CONTRA", "Pesquisando argumentos contrários"),
    (4, "ASSIGN_PIECES", "Atribuindo artefatos às peças"),
    (5, "GENERATE_MATCH", "Gerando partida"),
    (6, "EVALUATE_WINNER", "Avaliando vencedor"),
    (7, "BUILD_REPLAY", "Montando replay"),
]

# Orçamento máximo de lances (plies) por profundidade. NÃO é a duração do jogo: a partida termina por regra;
# se o orçamento esgotar antes, o estado é BUDGET_EXHAUSTED e a partida pode ser retomada.
DEPTH_PLIES_BUDGET = {
    "chess": {"quick": 60, "standard": 140, "deep": 260},
    "go": {"quick": 50, "standard": 110, "deep": 200},
}


class MatchStateConflictError(RuntimeError):
    """Operação inválida para o estado atual do Research Match (ex.: retomar partida já concluída)."""


class ResearchMatchOrchestrator(PreparationMixin, PlayMixin, ConclusionMixin, RecordingMixin):
    def __init__(self, session_manager: Any):
        self.sm = session_manager

    # ------------------------------------------------------------------ estado
    def init_match_state(self, sess: Dict[str, Any], depth: Optional[str] = None) -> Dict[str, Any]:
        game = sess["game"]
        chosen = depth or sess.get("depth") or "standard"
        if chosen not in DEPTH_PLIES_BUDGET[game]:
            chosen = "standard"
        sess["depth"] = chosen
        # Xadrez: Brancas iniciam (Pró = brancas). Go: Pretas iniciam (Pró = pretas).
        pro_color = "white" if game == "chess" else "black"
        state = ResearchMatchStateSchema(
            session_id=sess["id"],
            status="NOT_STARTED",
            depth=chosen,
            execution_mode=sess["execution_mode"],
            plies_budget=DEPTH_PLIES_BUDGET[game][chosen],
            pro_color=pro_color,
            contra_color="black" if pro_color == "white" else "white",
            stages=[
                MatchStageInfoSchema(index=i, key=k, label=l, status="pending").model_dump()
                for i, k, l in STAGE_DEFINITIONS
            ],
        ).model_dump()
        sess["research_match"] = state
        sess["_match_internal"] = {"pro_raw": None, "contra_raw": None, "play": None, "highlights": []}
        return state

    def get_match_state(self, session_id: str) -> Dict[str, Any]:
        sess = self._sess(session_id)
        return sess.get("research_match") or self.init_match_state(sess)

    def _sess(self, session_id: str) -> Dict[str, Any]:
        sess = self.sm.sessions.get(session_id)
        if not sess:
            raise KeyError(f"Sessão {session_id} não encontrada.")
        return sess

    # ------------------------------------------------------------------ visão por lado (Regra de Ouro)
    def get_pieces_for_viewer(
        self, session_id: str, viewer_side: Optional[str] = None, role: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        v2.3 C12 / SEC01: Controle estrito de acesso e privacidade de dossiês não jogados.
        Papéis: 'owner', 'white', 'black', 'observer'.
        Durante a partida em andamento:
          - 'owner': visualização integral
          - 'white': dossiês de white completos; black apenas jogados
          - 'black': dossiês de black completos; white apenas jogados
          - 'observer' (padrão quando viewer_side não informado): apenas peças já jogadas de ambos os lados
        Após conclusão: todos revelados no replay.
        """
        sess = self._sess(session_id)
        mstate = sess.get("research_match")
        if not mstate:
            return []
        pieces = copy.deepcopy(mstate.get("pieces", []))
        if mstate.get("is_complete"):
            return pieces

        effective_role = role or viewer_side or "observer"
        effective_role = effective_role.strip().lower()

        if effective_role in ("owner", "admin"):
            return pieces

        for p in pieces:
            if effective_role in ("white", "black") and p["color"] == effective_role:
                continue

            has_played = bool(p.get("history")) or any(
                a.get("played_at_ply") is not None for a in p.get("supporting_artifacts", [])
            )
            if not has_played:
                p["claim"] = "[reservada — ainda não jogada no tabuleiro]"
                p["supporting_artifacts"] = []
                p["counter_artifacts"] = []
            else:
                p["supporting_artifacts"] = [
                    a for a in p.get("supporting_artifacts", []) if a.get("played_at_ply") is not None
                ]
                p["counter_artifacts"] = []
        return pieces

    # ------------------------------------------------------------------ execução por estágio
    def run_next_stage(self, session_id: str, depth: Optional[str] = None) -> Dict[str, Any]:
        sess = self._sess(session_id)
        mstate = self._ensure_state(sess, depth)
        if mstate["is_complete"]:
            return mstate

        idx = mstate["current_stage"] + 1
        stage = mstate["stages"][idx - 1]
        stage["status"], stage["detail"] = "running", None
        sess["status"] = "RUNNING"
        if mstate.get("status") in (None, "NOT_STARTED"):
            mstate["status"] = "IN_PROGRESS"
        try:
            detail = self._execute_stage(sess, mstate, idx)
        except Exception as exc:  # estágio falhou: o que já existe é preservado e o estágio pode ser repetido
            stage["status"], stage["detail"] = "failed", str(exc)
            sess["status"] = "PAUSED"
            sess["last_error"] = str(exc)
            raise
        stage["status"], stage["detail"] = "completed", detail
        mstate["current_stage"] = idx
        mstate["percent_complete"] = int(round(idx / 7 * 100))
        self.sm._append_session_event(
            session_id, "MATCH_STAGE_COMPLETED",
            {"stage_index": idx, "stage_key": stage["key"], "detail": detail, "percent_complete": mstate["percent_complete"]},
        )
        sess["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return mstate

    def _ensure_state(self, sess: Dict[str, Any], depth: Optional[str]) -> Dict[str, Any]:
        """Cria o estado se não existir; antes do 1º estágio, permite trocar a profundidade."""
        mstate = sess.get("research_match")
        if not mstate or (mstate["current_stage"] == 0 and depth and mstate["depth"] != depth):
            mstate = self.init_match_state(sess, depth=depth)
        return mstate

    def run_full_match(self, session_id: str, depth: Optional[str] = None) -> Dict[str, Any]:
        sess = self._sess(session_id)
        self._ensure_state(sess, depth)
        while not sess["research_match"]["is_complete"]:
            self.run_next_stage(session_id, depth=depth)
        return sess["research_match"]

    def resume_match(self, session_id: str, extra_plies: Optional[int] = None) -> Dict[str, Any]:
        """Retoma uma partida interrompida por orçamento: amplia o orçamento e refaz os estágios 5–7."""
        sess = self._sess(session_id)
        mstate = sess.get("research_match")
        if not mstate or not mstate.get("resumable"):
            raise MatchStateConflictError(
                "NOT_RESUMABLE: somente partidas interrompidas por orçamento (BUDGET_EXHAUSTED) podem ser retomadas."
            )
        extra = extra_plies or DEPTH_PLIES_BUDGET[sess["game"]][mstate["depth"]]
        mstate["plies_budget"] += extra
        sess["max_steps"] = sess["budget"]["max_steps"] = mstate["plies_budget"]
        mstate["current_stage"] = 4
        mstate["is_complete"] = False
        mstate["resumable"] = False
        mstate["status"] = "IN_PROGRESS"
        mstate["conclusion"] = None
        for st in mstate["stages"][4:]:
            st["status"], st["detail"] = "pending", None
        mstate["percent_complete"] = int(round(4 / 7 * 100))
        sess["status"] = "RUNNING"
        self.sm._append_session_event(
            session_id, "MATCH_RESUMED",
            {"extra_plies": extra, "plies_budget": mstate["plies_budget"], "plies_played": mstate["plies_played"]},
        )
        return self.run_full_match(session_id)

    def _execute_stage(self, sess: Dict[str, Any], mstate: Dict[str, Any], idx: int) -> str:
        if idx == 1:
            return self._stage_1_build_sides(sess, mstate)
        if idx == 2:
            return self._stage_2_research_side(sess, mstate, side="pro")
        if idx == 3:
            return self._stage_2_research_side(sess, mstate, side="contra")
        if idx == 4:
            return self._stage_4_assign_pieces(sess, mstate)
        if idx == 5:
            return self._stage_5_generate_match(sess, mstate)
        if idx == 6:
            return self._stage_6_evaluate_winner(sess, mstate)
        return self._stage_7_build_replay(sess, mstate)
