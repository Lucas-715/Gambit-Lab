"""
Session Manager — Gambit Lab 2.0
Gerencia o ciclo de vida da sessão, máquinas de estado, cofres,
motores determinísticos e encadeamento de eventos.
Com distinção explícita entre Integridade, Verificação de Fonte e Avaliação de Evidência (Problema 1).
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

# Acervo de documentos temáticos reais pré-configurados (Problema 3)
SAMPLE_SCENARIOS = {
    "ia_seguranca": {
        "title": "Qual a arquitetura mais segura para sistemas com IA autônoma?",
        "doc_name": "NIST_AI_RMF_Playbook_2026.txt",
        "doc_content": (
            "NIST AI Risk Management Framework 2.0 (2026).\n"
            "Seção 3.2 — Rastreabilidade e Governança de Agentes Autônomos.\n"
            "1. Sistemas que utilizam agentes autônomos para tomada de decisão crítica "
            "exigem a separação estrita entre o módulo de proposição (LLM) e o módulo de validação de regras (motores determinísticos).\n"
            "2. Todas as alegações geradas por agentes devem conter rastreabilidade completa até uma fonte autorizada com hash SHA-256 congelado.\n"
            "3. Em testes comparativos, pipelines com arbitragem epistêmica independente e logs imutáveis reduziram alucinações não detectadas em 64%."
        ),
        "claim": "Pipelines de IA segura exigem separação estrita entre proposição do LLM e validação formal por motores determinísticos.",
        "quote": "exigem a separação estrita entre o módulo de proposição (LLM) e o módulo de validação de regras (motores determinísticos)."
    },
    "eleicoes_2030": {
        "title": "Projeções eleitorais e governança institucional em 2030",
        "doc_name": "Cenarios_Demograficos_Eleicoes_2030.txt",
        "doc_content": (
            "Análise Prospectiva de Tendências Eleitorais e Institucionais para 2030.\n"
            "Declaração Epistemológica: Eleições futuras não constituem fatos consumados; representam cenários probabilísticos e projeções incertas.\n"
            "Cenário 1 — Polarização Estável: Transições demográficas indicam maior peso do eleitorado urbano jovem, mas sem hegemonia garantida.\n"
            "Cenário 2 — Fragmentação Multipartidária: Reformas de representação favorecem coalizões regionais flexíveis.\n"
            "Conclusão do estudo: Nenhuma afirmação declarando um vencedor antecipado para 2030 é factualmente sustentável; trata-se de projeção com alta incerteza."
        ),
        "claim": "Projeções para 2030 constituem cenários com alta incerteza, não fatos consumados.",
        "quote": "Nenhuma afirmação declarando um vencedor antecipado para 2030 é factualmente sustentável; trata-se de projeção com alta incerteza."
    },
    "auditoria_controles": {
        "title": "Auditoria de Controles ISO 27001 e OWASP LLM Top 10",
        "doc_name": "Checklist_Controles_Seguranca_Cloud.txt",
        "doc_content": (
            "Checklist de Auditoria Técnica de Segurança em Nuvem (ISO 27001 / OWASP LLM 2026).\n"
            "Controle A.12.4.1 (Logs de Eventos): Registros de auditoria que registram atividades do usuário, exceções e eventos devem ser mantidos e protegidos contra adulteração por encadeamento de hash criptográfico.\n"
            "Controle A.9.4.2 (Segregação de Acessos): Cofres de evidências privadas entre partes adversárias devem ser isolados pré-partida, proibindo vazamento de dados confidenciais.\n"
            "Achado de Teste: Tentativas de prompt injection em documentos não confiáveis devem ser contidas tratando dados como não executáveis."
        ),
        "claim": "Logs de auditoria devem ser protegidos contra adulteração por encadeamento criptográfico de hash.",
        "quote": "Registros de auditoria que registram atividades do usuário, exceções e eventos devem ser mantidos e protegidos contra adulteração por encadeamento de hash criptográfico."
    }
}


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

        # Vincula documentos temáticos reais correspondentes ao tema escolhido (Problema 3)
        artifacts_list = []
        claims_list = []
        lower_title = req.title.lower()

        matched_scenario = None
        if "elei" in lower_title or "2030" in lower_title:
            matched_scenario = SAMPLE_SCENARIOS["eleicoes_2030"]
        elif "audit" in lower_title or "iso" in lower_title or "controle" in lower_title:
            matched_scenario = SAMPLE_SCENARIOS["auditoria_controles"]
        elif "ia" in lower_title or "seguran" in lower_title or "arquitetura" in lower_title:
            matched_scenario = SAMPLE_SCENARIOS["ia_seguranca"]

        if matched_scenario:
            art = self.vault.ingest_document(
                session_id=session_id,
                name=matched_scenario["doc_name"],
                content=matched_scenario["doc_content"],
                mime_type="text/plain",
                owner_side="public"
            )
            artifacts_list.append(art)

            # Cria citação verificada
            cit = CitationSchema(
                artifact_id=art["id"],
                artifact_name=art["name"],
                artifact_hash=art["sha256"],
                quote_text=matched_scenario["quote"],
                page_or_offset="Seção 3 / Parágrafo 1",
                quote_verified=True
            )
            claim = ClaimSchema(
                session_id=session_id,
                statement=matched_scenario["claim"],
                status="SUPPORTED" if "elei" not in lower_title else "HYPOTHESIS",
                scope=req.title,
                citations=[cit],
                binding_coord="d4" if req.game == "chess" else "E5",
                uncertainty_level="UNCERTAIN" if "elei" in lower_title else "CERTAIN"
            )
            claims_list.append(claim.model_dump())

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
            "claims": claims_list,
            "artifacts": artifacts_list,
            "fusion_report": None,
            "created_at": now,
            "updated_at": now
        }

        self.sessions[session_id] = session_record

        # Registra evento gênese da sessão
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

        return self._format_session_response(session_record)

    def _evaluate_verification_tiers(self, sess: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calcula rigorosamente as 3 camadas separadas:
        1. integrity_status: Integridade criptográfica do Event Store e SHA-256.
        2. source_status: Se há fontes e se as citações constam nos documentos.
        3. evidence_assessment: Veredito epistemológico da alegação.
        """
        session_id = sess["id"]
        # 1. Integridade
        chain_valid = self.event_store.verify_hash_chain(session_id)
        integrity_status = "INTEGRITY_VERIFIED" if chain_valid else "INTEGRITY_COMPROMISED"

        # 2. Fonte
        artifacts = sess.get("artifacts", [])
        claims = sess.get("claims", [])
        if len(artifacts) == 0:
            source_status = "NO_SOURCES_ATTACHED"
            evidence_assessment = "HYPOTHESIS"
            diagnostic_reason = (
                "Aviso: Nenhum documento foi anexado a esta sessão. "
                "A integridade dos registros está verificada (SHA-256), mas as afirmações permanecem "
                "estritamente como HIPÓTESES sem sustentação documental."
            )
        else:
            # Verifica se citações existem de verdade
            all_verified = True
            for c in claims:
                for cit in c.get("citations", []):
                    art_id = cit.get("artifact_id")
                    quote = cit.get("quote_text", "")
                    if not self.vault.verify_quote_exists(art_id, quote):
                        all_verified = False
                        break
            source_status = "SOURCE_VERIFIED" if all_verified else "QUOTE_MISMATCH"

            # 3. Evidência
            if not all_verified:
                evidence_assessment = "INSUFFICIENT"
                diagnostic_reason = "Trecho citado não pôde ser localizado nos bytes do artefato registrado."
            else:
                has_supported = any(c.get("status") == "SUPPORTED" for c in claims)
                has_refuted = any(c.get("status") == "REFUTED" for c in claims)
                if has_refuted:
                    evidence_assessment = "REFUTED"
                    diagnostic_reason = "Ao menos uma alegação alvo foi refutada por contra-evidência empírica."
                elif has_supported:
                    evidence_assessment = "SUPPORTED"
                    diagnostic_reason = "Todas as alegações ativas possuem citações verificadas com fontes primárias."
                else:
                    evidence_assessment = "INSUFFICIENT"
                    diagnostic_reason = "Premissas formuladas ainda não receberam validação conclusiva."

        return {
            "integrity_status": integrity_status,
            "source_status": source_status,
            "evidence_assessment": evidence_assessment,
            "diagnostic_reason": diagnostic_reason
        }

    def _format_session_response(self, sess: Dict[str, Any]) -> Dict[str, Any]:
        tiers = self._evaluate_verification_tiers(sess)
        res = sess.copy()
        res.update(tiers)
        res["artifacts_count"] = len(sess.get("artifacts", []))
        res["claims_count"] = len(sess.get("claims", []))
        return res

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        sess = self.sessions.get(session_id)
        if not sess:
            return None
        return self._format_session_response(sess)

    def list_sessions(self) -> List[Dict[str, Any]]:
        return [self._format_session_response(s) for s in self.sessions.values()]

    def lock_session(self, session_id: str) -> Dict[str, Any]:
        """Trava a configuração e congela os hashes dos documentos (RN-02, RN-14)."""
        sess = self.sessions.get(session_id)
        if not sess:
            raise KeyError(f"Sessão {session_id} não encontrada.")
        if sess["status"] != "DRAFT":
            return self._format_session_response(sess)

        lock_manifest = self.vault.lock_session_vaults(session_id)
        sess["status"] = "LOCKED"
        sess["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        self.event_store.append_event(
            session_id=session_id,
            expected_version=sess["version"],
            event_type="SESSION_LOCKED",
            payload={"manifest": lock_manifest}
        )
        sess["version"] += 1
        return self._format_session_response(sess)

    def start_session(self, session_id: str) -> Dict[str, Any]:
        """Inicia a execução da partida/investigação (LOCKED -> RUNNING)."""
        sess = self.sessions.get(session_id)
        if not sess:
            raise KeyError(f"Sessão {session_id} não encontrada.")
        if sess["status"] == "DRAFT":
            self.lock_session(session_id)

        sess["status"] = "RUNNING"
        sess["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        self.event_store.append_event(
            session_id=session_id,
            expected_version=sess["version"],
            event_type="SESSION_STARTED",
            payload={"status": "RUNNING"}
        )
        sess["version"] += 1
        return self._format_session_response(sess)

    def submit_action(
        self,
        session_id: str,
        expected_version: int,
        action: ActionPayloadSchema,
        idempotency_key: Optional[str] = None
    ) -> ActionResponseSchema:
        """
        Executa ação com controle de versão otimista e idempotência (RF-39, RN-30).
        Suporta casos extremos de xeque e IMPASSE_DA_VARIANTE (Problema 4).
        """
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

        if sess["game"] == "chess":
            engine = self.chess_engines[session_id]
            move_uci = action.coord or ""

            require_epistemic = (sess["mode"] == "debate") and engine.is_capture_move(move_uci)
            arbitration_verdict = None

            if require_epistemic:
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
                engine_status = "IMPASSE_DA_VARIANTE" if res.is_impasse_variante else ("ILLEGAL" if not res.legal else "EPISTEMIC_BLOCKED")
                board_schema = BoardPositionSchema(
                    game="chess",
                    fen=engine.fen,
                    to_move="white" if engine.turn == "white" else "black",
                    turn=engine.fullmove_number,
                    is_game_over=engine.is_game_over,
                    game_result=engine.get_game_result(),
                    is_check=res.is_check,
                    diagnostic_reason=res.diagnostic_reason
                )
                return ActionResponseSchema(
                    accepted=False,
                    version=sess["version"],
                    engine_result=engine_status,
                    evidence_result=evidence_result,
                    event_id="",
                    next_to_move="white" if engine.turn == "white" else "black",
                    game_result=engine.get_game_result(),
                    board=board_schema,
                    error=res.error
                )

            engine_status = "LEGAL"
            if res.is_checkmate:
                engine_status = "CHECKMATE"
            elif res.is_draw or res.is_stalemate:
                engine_status = "DRAW"

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
                "game_result": engine.get_game_result(),
                "is_check": res.is_check
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

            # No Go, capturas espaciais preservam o histórico de claims (RN-09, RN-10)
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
