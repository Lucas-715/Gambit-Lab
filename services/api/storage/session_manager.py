"""
Session Manager — Gambit Lab 2.0
Gerencia o ciclo de vida da sessão, máquinas de estado, cofres,
motores determinísticos e encadeamento de eventos.
"""
from typing import Dict, Any, List, Optional
import uuid
import datetime
from packages.game_rules.chess_engine import EpistemicChessEngine
from packages.game_rules.go_engine import GoEngine9x9
from services.api.storage.event_store import EventStore, ConcurrencyConflictError
from services.api.storage.vault import DocumentVault, DocumentAccessForbiddenError
from services.api.agents.gemini_adapter import GeminiAdapter
from services.api.fusion.pipeline import FusionOrchestrator
from services.api.models.schemas import (
    CreateSessionRequest,
    SessionResponseSchema,
    BoardPositionSchema,
    ActionPayloadSchema,
    ActionResponseSchema,
    ClaimSchema,
    CitationSchema,
    SessionBudget
)


class SessionManager:
    """
    Coordenador central em memória para instâncias de sessões ativas do MVP.
    """

    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.chess_engines: Dict[str, EpistemicChessEngine] = {}
        self.go_engines: Dict[str, GoEngine9x9] = {}
        self.event_store = EventStore()
        self.vault = DocumentVault()
        self.gemini_adapter = GeminiAdapter()
        self.fusion_orchestrator = FusionOrchestrator(self.gemini_adapter)
        self.idempotency_cache: Dict[str, Dict[str, Any]] = {}

    def create_session(self, req: CreateSessionRequest) -> Dict[str, Any]:
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        budget = req.budget.model_dump() if req.budget else {
            "max_calls": 15,
            "max_tokens": 50000,
            "current_calls": 0,
            "current_tokens": 0
        }

        if req.game == "chess":
            engine = EpistemicChessEngine()
            self.chess_engines[session_id] = engine
            board = BoardPositionSchema(
                game="chess",
                fen=engine.fen,
                to_move="white",
                turn=1,
                captured_white=0,
                captured_black=0,
                is_game_over=False
            ).model_dump()
        else:
            engine = GoEngine9x9(komi=6.5)
            self.go_engines[session_id] = engine
            board = BoardPositionSchema(
                game="go",
                stones=[],
                to_move="black",
                turn=1,
                captured_white=0,
                captured_black=0,
                komi=6.5,
                is_game_over=False
            ).model_dump()

        session_record = {
            "id": session_id,
            "title": req.title,
            "mode": req.mode,
            "game": req.game,
            "status": "DRAFT",
            "version": 1,
            "source_policy": req.source_policy,
            "budget": budget,
            "board": board,
            "active_branch_id": None,
            "branches": [],
            "claims": [],
            "artifacts": [],
            "fusion_report": None,
            "created_at": now,
            "updated_at": now
        }

        self.sessions[session_id] = session_record

        # Registra evento de criação da sessão
        self.event_store.append_event(
            session_id=session_id,
            expected_version=1,
            event_type="SESSION_CREATED",
            payload={
                "title": req.title,
                "mode": req.mode,
                "game": req.game,
                "source_policy": req.source_policy
            }
        )

        return session_record

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self.sessions.get(session_id)

    def list_sessions(self) -> List[Dict[str, Any]]:
        return list(self.sessions.values())

    def lock_session(self, session_id: str) -> Dict[str, Any]:
        """Trava a configuração e congela os hashes dos documentos (RN-02, RN-14)."""
        sess = self.sessions.get(session_id)
        if not sess:
            raise KeyError(f"Sessão {session_id} não encontrada.")
        if sess["status"] != "DRAFT":
            return sess

        lock_manifest = self.vault.lock_session_vaults(session_id)
        sess["status"] = "LOCKED"
        sess["version"] += 1
        sess["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        self.event_store.append_event(
            session_id=session_id,
            expected_version=sess["version"] - 1,
            event_type="SESSION_LOCKED",
            payload={"manifest": lock_manifest}
        )
        return sess

    def start_session(self, session_id: str) -> Dict[str, Any]:
        """Inicia a execução da partida/investigação (LOCKED -> RUNNING)."""
        sess = self.sessions.get(session_id)
        if not sess:
            raise KeyError(f"Sessão {session_id} não encontrada.")
        if sess["status"] == "DRAFT":
            sess = self.lock_session(session_id)

        sess["status"] = "RUNNING"
        sess["version"] += 1
        sess["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        self.event_store.append_event(
            session_id=session_id,
            expected_version=sess["version"] - 1,
            event_type="SESSION_STARTED",
            payload={"status": "RUNNING"}
        )
        return sess

    def submit_action(
        self,
        session_id: str,
        expected_version: int,
        action: ActionPayloadSchema,
        idempotency_key: Optional[str] = None
    ) -> ActionResponseSchema:
        """
        Executa ação com controle de versão otimista e idempotência (RF-39, RN-30).
        """
        # Checa idempotência
        if idempotency_key and idempotency_key in self.idempotency_cache:
            cached = self.idempotency_cache[idempotency_key]
            return ActionResponseSchema(**cached)

        sess = self.sessions.get(session_id)
        if not sess:
            raise KeyError(f"Sessão {session_id} não encontrada.")

        if sess["version"] != expected_version:
            raise ConcurrencyConflictError(
                f"Conflito de concorrência: versão esperada {expected_version}, versão atual {sess['version']}."
            )

        if sess["status"] == "DRAFT":
            sess["status"] = "RUNNING"

        evidence_result = "NOT_APPLICABLE"
        claim_rec = None

        if sess["game"] == "chess":
            engine = self.chess_engines[session_id]
            move_uci = action.coord or ""

            # Se for debate e o lance for captura, exige arbitragem epistêmica (RN-06, RF-15)
            require_epistemic = (sess["mode"] == "debate") and engine.is_capture_move(move_uci)
            arbitration_verdict = None

            if require_epistemic:
                # Simula julgamento do árbitro sobre a alegação alvo
                adjudication = self.gemini_adapter.call_debate_adjudication(
                    topic=sess["title"],
                    claim_statement="Alegação sob contestação",
                    citation_quote="Dados empíricos apresentados pelo atacante refutam a tese",
                    counter_quote="Contraprova direta",
                    budget=sess["budget"]
                )
                arbitration_verdict = adjudication["verdict"]
                evidence_result = arbitration_verdict

            res = engine.validate_and_apply_move(
                move_uci=move_uci,
                arbitration_verdict=arbitration_verdict,
                require_epistemic_capture=require_epistemic
            )

            if not res.legal or res.epistemic_blocked:
                # Lance rejeitado: o tabuleiro e a versão NÃO mudam (RN-04, RN-05, AC-13)
                board_schema = BoardPositionSchema(
                    game="chess",
                    fen=engine.fen,
                    to_move="white" if engine.turn == "white" else "black",
                    turn=engine.fullmove_number,
                    is_game_over=engine.is_game_over,
                    game_result=engine.get_game_result()
                )
                return ActionResponseSchema(
                    accepted=False,
                    version=sess["version"],
                    engine_result="ILLEGAL" if not res.legal else "IMPASSE_DA_VARIANTE",
                    evidence_result=evidence_result,
                    event_id="",
                    next_to_move="white" if engine.turn == "white" else "black",
                    board=board_schema,
                    error=res.error
                )

            engine_status = "LEGAL"
            if res.is_checkmate:
                engine_status = "CHECKMATE"
            elif res.is_draw or res.is_stalemate:
                engine_status = "DRAW"

            # Registra claim associado, se fornecido
            if action.claim_id:
                claim_rec = {
                    "id": action.claim_id,
                    "session_id": session_id,
                    "statement": f"Alegação vinculada ao lance {res.san}",
                    "status": "SUPPORTED" if evidence_result != "REFUTED" else "REFUTED",
                    "scope": "Ação de tabuleiro",
                    "binding_coord": move_uci
                }
                sess["claims"].append(claim_rec)

            sess["board"] = {
                "game": "chess",
                "fen": res.fen_after,
                "to_move": "white" if engine.turn == "white" else "black",
                "turn": engine.fullmove_number,
                "captured_white": len([m for m in engine.move_history if m.get("is_capture") and m.get("turn") == "white"]),
                "captured_black": len([m for m in engine.move_history if m.get("is_capture") and m.get("turn") == "black"]),
                "is_game_over": engine.is_game_over,
                "game_result": engine.get_game_result()
            }

            event_record = self.event_store.append_event(
                session_id=session_id,
                expected_version=sess["version"],
                event_type="CHESS_MOVE",
                payload={
                    "uci": move_uci,
                    "san": res.san,
                    "fen": res.fen_after,
                    "is_capture": res.is_capture,
                    "engine_result": engine_status,
                    "evidence_result": evidence_result,
                    "claim_id": action.claim_id
                }
            )

        else:
            # Go 9x9 Engine
            go_engine = self.go_engines[session_id]
            coord_str = action.coord or "PASS"
            go_res = go_engine.play_move(coord_str)

            if not go_res.legal:
                board_schema = BoardPositionSchema(
                    game="go",
                    stones=go_engine.to_dict()["stones"],
                    to_move="black" if go_engine.turn == "B" else "white",
                    turn=len(go_engine.move_history) + 1,
                    is_game_over=go_engine.is_game_over,
                    game_result=go_engine.game_result
                )
                return ActionResponseSchema(
                    accepted=False,
                    version=sess["version"],
                    engine_result="ILLEGAL",
                    evidence_result="NOT_APPLICABLE",
                    event_id="",
                    next_to_move="black" if go_engine.turn == "B" else "white",
                    board=board_schema,
                    error=go_res.error
                )

            # Em Go, a captura é estritamente espacial (RN-09, RN-10)
            if go_res.is_capture:
                evidence_result = "SPATIAL_CAPTURE_MAINTAINS_CLAIMS"

            if action.claim_id:
                claim_rec = {
                    "id": action.claim_id,
                    "session_id": session_id,
                    "statement": f"Alegação associada à pedra {coord_str}",
                    "status": "SUPPORTED",
                    "scope": "Região Go",
                    "binding_coord": coord_str
                }
                sess["claims"].append(claim_rec)

            sess["board"] = {
                "game": "go",
                "stones": go_engine.to_dict()["stones"],
                "to_move": "black" if go_engine.turn == "B" else "white",
                "turn": len(go_engine.move_history) + 1,
                "captured_white": go_engine.captured_by_black,
                "captured_black": go_engine.captured_by_white,
                "komi": go_engine.komi,
                "is_game_over": go_engine.is_game_over,
                "game_result": go_engine.game_result
            }

            event_record = self.event_store.append_event(
                session_id=session_id,
                expected_version=sess["version"],
                event_type="GO_MOVE",
                payload={
                    "coord": coord_str,
                    "is_capture": go_res.is_capture,
                    "captured_count": len(go_res.captured_stones),
                    "evidence_result": evidence_result,
                    "claim_id": action.claim_id
                }
            )

        sess["version"] += 1
        sess["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        response = ActionResponseSchema(
            accepted=True,
            version=sess["version"],
            engine_result="LEGAL",
            evidence_result=evidence_result,
            event_id=event_record["event_id"],
            next_to_move=sess["board"]["to_move"],
            game_result=sess["board"].get("game_result"),
            board=BoardPositionSchema(**sess["board"])
        )

        if idempotency_key:
            self.idempotency_cache[idempotency_key] = response.model_dump()

        return response
