"""
Session Manager & Investigation Orchestrator — Gambit Lab Nocturne (R1.0)
Gerencia o ciclo de vida completo da sessão, máquina de estados (DRAFT, READY, RUNNING,
AWAITING_INPUT, PAUSED, BUDGET_EXHAUSTED, COMPLETED, FAILED, CANCELLED),
orquestração contínua multi-turno sem limite artificial de 3 lances (`advance_investigation`),
integração auditável de Pesquisa Web opt-in (`OWN_ONLY | WEB_ONLY | HYBRID`),
telemetria honesta de execução (`DEMO_OFFLINE | LIVE_DOCUMENTS | LIVE_WEB | LIVE_HYBRID`)
e separação estrita das 3 camadas de verificação epistêmica.
(AUD-01..AUD-04, P0-A..P0-C, AT-01..AT-24)
"""
from typing import Dict, Any, List, Optional
import uuid
import datetime
from packages.game_rules.chess_engine import EpistemicChessEngine
from packages.game_rules.go_engine import GoEngine9x9
from services.api.storage.event_store import EventStore, ConcurrencyConflictError
from services.api.storage.vault import DocumentVault, DocumentAccessForbiddenError
from services.api.agents.gemini_adapter import (
    GeminiAdapter,
    BudgetExceededError,
    ProviderUnavailableError,
    is_future_projection_topic,
    contains_prompt_injection_attempt,
)
from services.api.agents.web_search_adapter import (
    WebSearchAdapter,
    WebSearchUnavailableError,
    SSRFBlockedError,
)
from services.api.fusion.pipeline import FusionOrchestrator
from services.api.models.schemas import (
    CreateSessionRequest,
    BoardPositionSchema,
    ActionPayloadSchema,
    ActionResponseSchema,
    AdvanceSessionRequest,
    AdvanceSessionResponse,
    ProviderUsageSchema,
    ClaimSchema,
    CitationSchema,
    JudgmentSchema,
    RubricEvaluation,
    normalize_source_policy,
)


class SessionStateConflictError(Exception):
    """Lançada quando uma operação é inválida para o estado atual da sessão (HTTP 409)."""
    pass


# Fixture documental estrita usada apenas quando o prompt corresponde exatamente ao caso canônico
# ou quando use_demo_fixture=True é solicitado explicitamente.
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
        "quote": "exigem a separação estrita entre o módulo de proposição (LLM) e o módulo de validação de regras (motores determinísticos).",
    }
}


class SessionManager:
    """
    Coordenador central de sessões, motores determinísticos, cofres, busca web e orquestração multiagente.
    """

    def __init__(
        self,
        gemini_adapter: Optional[GeminiAdapter] = None,
        web_search_adapter: Optional[WebSearchAdapter] = None,
    ):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.chess_engines: Dict[str, EpistemicChessEngine] = {}
        self.go_engines: Dict[str, GoEngine9x9] = {}
        self.event_store = EventStore()
        self.vault = DocumentVault()
        self.gemini_adapter = gemini_adapter or GeminiAdapter()
        self.web_search_adapter = web_search_adapter or WebSearchAdapter()
        self.fusion_orchestrator = FusionOrchestrator(self.gemini_adapter)
        self.idempotency_cache: Dict[str, Dict[str, Any]] = {}
        self.advance_idempotency_cache: Dict[str, Dict[str, Any]] = {}

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "app": "Gambit Lab Nocturne",
            "version": "2.1.0-nocturne",
            "gemini": self.gemini_adapter.get_capabilities(),
            "web_search": self.web_search_adapter.get_capabilities(),
            "supported_policies": ["OWN_ONLY", "WEB_ONLY", "HYBRID"],
            "supported_execution_modes": [
                "DEMO_OFFLINE",
                "LIVE_DOCUMENTS",
                "LIVE_WEB",
                "LIVE_HYBRID",
            ],
            "supported_games": ["chess", "go"],
            "supported_modes": ["research", "debate", "audit"],
            "default_max_steps": 12,
        }

    def _resolve_execution_mode(self, norm_policy: str, force_demo: Optional[bool]) -> str:
        gemini_caps = self.gemini_adapter.get_capabilities()
        if force_demo is True or not gemini_caps["live_allowed"]:
            return "DEMO_OFFLINE"
        if norm_policy == "WEB_ONLY":
            return "LIVE_WEB"
        if norm_policy == "HYBRID":
            return "LIVE_HYBRID"
        return "LIVE_DOCUMENTS"

    def create_session(self, req: CreateSessionRequest) -> Dict[str, Any]:
        norm_policy = normalize_source_policy(req.source_policy)
        if norm_policy == "WEB_ONLY" and not self.web_search_adapter.is_enabled():
            raise WebSearchUnavailableError(
                "SEARCH_UNAVAILABLE: A política WEB_ONLY requer pesquisa web habilitada no servidor."
            )

        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        max_steps = req.budget.max_steps if req.budget else req.max_steps

        budget = (
            req.budget.model_dump()
            if req.budget
            else {
                "max_calls": max(24, max_steps * 2),
                "max_tokens": 120000,
                "max_steps": max_steps,
                "current_calls": 0,
                "current_tokens": 0,
                "current_steps": 0,
                "prompt_tokens": None,
                "completion_tokens": None,
                "last_latency_ms": None,
                "estimated_cost_usd": None,
                "usage_measured": False,
            }
        )
        budget["max_steps"] = max_steps

        execution_mode = self._resolve_execution_mode(norm_policy, req.force_demo)

        if req.game == "chess":
            engine = EpistemicChessEngine()
            self.chess_engines[session_id] = engine
            board = BoardPositionSchema(
                game="chess",
                fen=engine.fen,
                to_move="white",
                turn=1,
                ply_count=0,
                last_move=None,
                captured_white=0,
                captured_black=0,
                is_game_over=False,
            ).model_dump()
            default_strat = req.initial_strategy or "queen"
        else:
            engine = GoEngine9x9(komi=6.5)
            self.go_engines[session_id] = engine
            board = BoardPositionSchema(
                game="go",
                stones=[],
                to_move="black",
                turn=1,
                ply_count=0,
                last_move=None,
                captured_white=0,
                captured_black=0,
                komi=6.5,
                is_game_over=False,
            ).model_dump()
            default_strat = (
                req.initial_strategy
                if req.initial_strategy in ("influence", "territory", "invasion")
                else "influence"
            )

        artifacts_list: List[Dict[str, Any]] = []
        claims_list: List[Dict[str, Any]] = []

        # Anexa fixture canônico NIST AI RMF APENAS se solicitado explicitamente ou para a pergunta canônica de arquitetura de IA segura
        import re
        canonical_ia = SAMPLE_SCENARIOS["ia_seguranca"]
        lower_t = req.title.strip().lower()
        is_canonical_ia_arch = (
            "arquitetura" in lower_t
            and "segura" in lower_t
            and bool(re.search(r"\b(ia|ai)\b", lower_t))
        )
        if req.use_demo_fixture is True or (
            req.use_demo_fixture is not False
            and norm_policy == "OWN_ONLY"
            and is_canonical_ia_arch
        ):
            art = self.vault.ingest_document(
                session_id=session_id,
                name=canonical_ia["doc_name"],
                content=canonical_ia["doc_content"],
                mime_type="text/plain",
                owner_side="public",
                source_type="document",
            )
            artifacts_list.append(art)

            cit = CitationSchema(
                artifact_id=art["id"],
                artifact_name=art["name"],
                artifact_hash=art["sha256"],
                quote_text=canonical_ia["quote"],
                page_or_offset="Seção 3.2 / Item 1",
                quote_verified=True,
            )
            claim = ClaimSchema(
                session_id=session_id,
                statement=canonical_ia["claim"],
                status="SUPPORTED",
                scope=req.title,
                citations=[cit],
                binding_coord=None,
                step_index=0,
                ply_index=0,
                uncertainty_level="CERTAIN",
            )
            claims_list.append(claim.model_dump())

        provider_usage = ProviderUsageSchema(
            source="demo_offline" if execution_mode == "DEMO_OFFLINE" else "unmeasured",
            model=self.gemini_adapter.model if execution_mode != "DEMO_OFFLINE" else None,
        ).model_dump()

        session_record = {
            "id": session_id,
            "title": req.title,
            "mode": req.mode,
            "game": req.game,
            "strategy": default_strat,
            "status": "DRAFT",
            "execution_mode": execution_mode,
            "version": 1,
            "source_policy": req.source_policy,
            "normalized_source_policy": norm_policy,
            "ply_count": 0,
            "investigation_step_index": 0,
            "max_steps": max_steps,
            "budget": budget,
            "board": board,
            "active_branch_id": None,
            "branches": [],
            "claims": claims_list,
            "artifacts": artifacts_list,
            "messages": [
                {
                    "id": f"msg_{uuid.uuid4().hex[:8]}",
                    "role": "system",
                    "agent_label": "Orquestrador Nocturne",
                    "text": (
                        f"Sessão iniciada em modo {execution_mode} ({req.mode.upper()} / {req.game.upper()}) "
                        f"com política de fontes {norm_policy}."
                    ),
                    "step_index": 0,
                    "ply_index": 0,
                    "timestamp": now,
                }
            ],
            "judgments": [],
            "provider_usage": provider_usage,
            "web_queries_executed": [],
            "source_status_override": None,
            "fusion_report": None,
            "created_at": now,
            "updated_at": now,
        }

        self.sessions[session_id] = session_record

        self.event_store.append_event(
            session_id=session_id,
            expected_version=1,
            event_type="SESSION_CREATED",
            payload={
                "title": req.title,
                "mode": req.mode,
                "game": req.game,
                "source_policy": norm_policy,
                "execution_mode": execution_mode,
                "max_steps": max_steps,
            },
        )

        return self._format_session_response(session_record)

    def register_claim_with_citation(
        self,
        session_id: str,
        statement: str,
        artifact_id: Optional[str] = None,
        quote_text: Optional[str] = None,
        author_agent: str = "agent_pesquisador",
    ) -> Dict[str, Any]:
        """
        Registra e audita imediatamente uma alegação com citação contra o DocumentVault (útil para auditoria e AT-14).
        """
        sess = self.sessions.get(session_id)
        if not sess:
            raise KeyError(f"Sessão {session_id} não encontrada.")

        cits: List[CitationSchema] = []
        verdict = "NOT_ASSESSED"
        rationale = "Alegação registrada sem fonte vinculada."

        if artifact_id:
            art = self.vault.get_artifact(artifact_id)
            verified, offset = self.vault.find_verified_quote_offset(artifact_id, quote_text or "")
            cits.append(
                CitationSchema(
                    artifact_id=art["id"],
                    artifact_name=art["name"],
                    artifact_hash=art["sha256"],
                    quote_text=quote_text or "",
                    page_or_offset=offset or "unverified",
                    quote_verified=verified,
                    url=art.get("canonical_url") or art.get("url"),
                    domain=art.get("domain"),
                )
            )
            if not verified:
                verdict = "INSUFFICIENT"
                rationale = "QUOTE_MISMATCH: O trecho citado não existe literalmente nos bytes do artefato."
            elif contains_prompt_injection_attempt(art.get("content", "")):
                verdict = "INSUFFICIENT"
                rationale = "Instrução adversária detectada no documento; texto tratado como dado inerte."
            elif is_future_projection_topic(sess["title"]) or is_future_projection_topic(statement):
                verdict = "HYPOTHESIS"
                rationale = "Projeção futura: trecho contextual verificado, mas conclusão mantida como hipótese incerta."
            else:
                verdict = "SUPPORTED"
                rationale = f"Citação literal verificada em '{art['name']}' ({offset})."
        else:
            verdict = "HYPOTHESIS"

        claim = ClaimSchema(
            session_id=session_id,
            statement=statement,
            status=verdict,
            scope=sess["title"],
            citations=cits,
            author_agent=author_agent,
            step_index=sess["investigation_step_index"],
            ply_index=sess["ply_count"],
            uncertainty_level="PROJECTION" if is_future_projection_topic(statement) else (
                "CERTAIN" if verdict == "SUPPORTED" else "UNCERTAIN"
            ),
        )
        sess["claims"].append(claim.model_dump())

        judgment = JudgmentSchema(
            session_id=session_id,
            claim_id=claim.id,
            verdict=verdict,
            rubric=RubricEvaluation(
                excerpt_verification=(verdict == "SUPPORTED"),
                support_or_refutation_match=(verdict == "SUPPORTED"),
                uncertainty_recognized=True,
                role_conflict_free=True,
            ),
            rationale=rationale,
            evaluator_agent="agent_arbitro_epistemico",
        )
        sess["judgments"].append(judgment.model_dump())
        sess["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return self._format_session_response(sess)

    def _evaluate_verification_tiers(self, sess: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calcula com honestidade radical as 3 camadas separadas:
        1. integrity_status: Integridade criptográfica do Event Store e SHA-256.
        2. source_status: Presença de fontes e correspondência literal de citações.
        3. evidence_assessment: Veredito epistêmico (jamais SUPPORTED sem fonte + citação literal verificada).
        """
        session_id = sess["id"]
        chain_valid = self.event_store.verify_hash_chain(session_id)
        integrity_status = "INTEGRITY_VERIFIED" if chain_valid else "INTEGRITY_COMPROMISED"

        if sess.get("source_status_override") == "SEARCH_UNAVAILABLE":
            return {
                "integrity_status": integrity_status,
                "source_status": "SEARCH_UNAVAILABLE",
                "evidence_assessment": "NOT_ASSESSED",
                "diagnostic_reason": (
                    sess.get("web_search_diagnostic")
                    or "Pesquisa web indisponível nesta etapa; nenhuma fonte externa foi inventada."
                ),
            }

        artifacts = sess.get("artifacts", [])
        claims = sess.get("claims", [])

        if len(artifacts) == 0:
            # Verifica se algum claim tentou citar um artefato inexistente
            dangling_citations = any(len(c.get("citations", [])) > 0 for c in claims)
            if dangling_citations:
                return {
                    "integrity_status": integrity_status,
                    "source_status": "SOURCE_UNRESOLVED",
                    "evidence_assessment": "INSUFFICIENT",
                    "diagnostic_reason": "Alegação referencia fonte inexistente no cofre da sessão.",
                }
            return {
                "integrity_status": integrity_status,
                "source_status": "NO_SOURCES_ATTACHED",
                "evidence_assessment": "HYPOTHESIS",
                "diagnostic_reason": (
                    "Aviso: Nenhum documento foi anexado a esta sessão. "
                    "A integridade dos registros está verificada (SHA-256), mas as afirmações permanecem "
                    "estritamente como HIPÓTESES sem sustentação documental."
                ),
            }

        # Há artefatos anexados/recuperados: verifica citações reais
        total_citations = 0
        all_verified = True
        for c in claims:
            for cit in c.get("citations", []):
                total_citations += 1
                art_id = cit.get("artifact_id")
                quote = cit.get("quote_text", "")
                try:
                    if not art_id or not self.vault.verify_quote_exists(art_id, quote):
                        all_verified = False
                        break
                except KeyError:
                    all_verified = False
                    break
            if not all_verified:
                break

        if not all_verified:
            return {
                "integrity_status": integrity_status,
                "source_status": "QUOTE_MISMATCH",
                "evidence_assessment": "INSUFFICIENT",
                "diagnostic_reason": "QUOTE_MISMATCH: Trecho citado não pôde ser localizado literalmente nos bytes do artefato registrado.",
            }

        if total_citations == 0:
            # Existem documentos no cofre, mas nenhuma citação literal foi vinculada/avaliada ainda
            if len(claims) == 0:
                return {
                    "integrity_status": integrity_status,
                    "source_status": "NOT_ASSESSED",
                    "evidence_assessment": "NOT_ASSESSED",
                    "diagnostic_reason": "Fontes registradas com SHA-256 íntegro, aguardando extração e auditoria de citações.",
                }
            return {
                "integrity_status": integrity_status,
                "source_status": "SOURCE_UNRESOLVED",
                "evidence_assessment": "INSUFFICIENT",
                "diagnostic_reason": "Fontes anexadas não contêm citações literais vinculadas que sustentem as alegações atuais.",
            }

        source_status = "SOURCE_VERIFIED"
        has_supported = any(
            c.get("status") == "SUPPORTED" and c.get("uncertainty_level") != "PROJECTION"
            for c in claims
        )
        has_refuted = any(c.get("status") == "REFUTED" for c in claims)
        has_projection = any(c.get("uncertainty_level") == "PROJECTION" for c in claims)
        has_not_comparable = any(c.get("status") == "NOT_COMPARABLE" for c in claims)

        if has_refuted:
            evidence_assessment = "REFUTED"
            diagnostic_reason = "Ao menos uma alegação alvo foi refutada por contra-evidência empírica verificada."
        elif has_not_comparable and not has_supported:
            evidence_assessment = "NOT_COMPARABLE"
            diagnostic_reason = "As fontes comparadas utilizam métricas metodologicamente incompatíveis (NOT_COMPARABLE)."
        elif has_supported:
            evidence_assessment = "SUPPORTED"
            diagnostic_reason = "Alegações suportadas possuem citações literais verificadas nos artefatos/snapshots da sessão."
        elif has_projection:
            evidence_assessment = "HYPOTHESIS"
            diagnostic_reason = "Tema prospectivo/futuro: fontes verificadas contextualizam cenários, mas conclusões permanecem como projeções incertas."
        else:
            evidence_assessment = "INSUFFICIENT"
            diagnostic_reason = "Premissas formuladas ainda não receberam sustentação documental conclusiva."

        return {
            "integrity_status": integrity_status,
            "source_status": source_status,
            "evidence_assessment": evidence_assessment,
            "diagnostic_reason": diagnostic_reason,
        }

    def _format_session_response(self, sess: Dict[str, Any]) -> Dict[str, Any]:
        tiers = self._evaluate_verification_tiers(sess)
        events = self.event_store.get_events(sess["id"])
        public_artifacts = self.vault.list_artifacts_for_session(sess["id"])
        res = sess.copy()
        res.update(tiers)
        res["verification_tiers"] = tiers
        res["artifacts"] = public_artifacts
        res["artifacts_count"] = len(sess.get("artifacts", []))
        res["claims_count"] = len(sess.get("claims", []))
        res["events_count"] = len(events)
        return res

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        sess = self.sessions.get(session_id)
        if not sess:
            return None
        return self._format_session_response(sess)

    def list_sessions(self) -> List[Dict[str, Any]]:
        return [self._format_session_response(s) for s in self.sessions.values()]

    def _append_session_event(
        self, session_id: str, event_type: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        sess = self.sessions[session_id]
        evt = self.event_store.append_event(
            session_id=session_id,
            expected_version=sess["version"],
            event_type=event_type,
            payload=payload,
        )
        sess["version"] = evt["version"]
        sess["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return evt

    def lock_session(self, session_id: str) -> Dict[str, Any]:
        """Trava a configuração e congela os hashes dos documentos (RN-02, RN-14)."""
        sess = self.sessions.get(session_id)
        if not sess:
            raise KeyError(f"Sessão {session_id} não encontrada.")
        if sess["status"] != "DRAFT":
            return self._format_session_response(sess)

        lock_manifest = self.vault.lock_session_vaults(session_id)
        sess["status"] = "LOCKED"
        self._append_session_event(session_id, "SESSION_LOCKED", {"manifest": lock_manifest})
        return self._format_session_response(sess)

    def start_session(self, session_id: str) -> Dict[str, Any]:
        """Inicia a execução da partida/investigação (LOCKED -> RUNNING)."""
        sess = self.sessions.get(session_id)
        if not sess:
            raise KeyError(f"Sessão {session_id} não encontrada.")
        if sess["status"] == "DRAFT":
            self.lock_session(session_id)

        sess["status"] = "RUNNING"
        self._append_session_event(session_id, "SESSION_STARTED", {"status": "RUNNING"})
        return self._format_session_response(sess)

    def pause_session(self, session_id: str) -> Dict[str, Any]:
        sess = self.sessions.get(session_id)
        if not sess:
            raise KeyError(f"Sessão {session_id} não encontrada.")
        if sess["status"] in ("COMPLETED", "FINISHED", "CANCELLED"):
            raise SessionStateConflictError(f"Não é possível pausar sessão em estado {sess['status']}.")
        sess["status"] = "PAUSED"
        self._append_session_event(session_id, "SESSION_PAUSED", {"status": "PAUSED"})
        return self._format_session_response(sess)

    def resume_session(self, session_id: str) -> Dict[str, Any]:
        sess = self.sessions.get(session_id)
        if not sess:
            raise KeyError(f"Sessão {session_id} não encontrada.")
        if sess["status"] in ("COMPLETED", "FINISHED", "CANCELLED"):
            raise SessionStateConflictError(f"Não é possível retomar sessão em estado {sess['status']}.")
        sess["status"] = "AWAITING_INPUT"
        self._append_session_event(session_id, "SESSION_RESUMED", {"status": "AWAITING_INPUT"})
        return self._format_session_response(sess)

    def cancel_session(self, session_id: str) -> Dict[str, Any]:
        sess = self.sessions.get(session_id)
        if not sess:
            raise KeyError(f"Sessão {session_id} não encontrada.")
        sess["status"] = "CANCELLED"
        self._append_session_event(session_id, "SESSION_CANCELLED", {"status": "CANCELLED"})
        return self._format_session_response(sess)

    def advance_investigation(
        self,
        session_id: str,
        req: AdvanceSessionRequest,
        idempotency_key: Optional[str] = None,
    ) -> AdvanceSessionResponse:
        """
        Orquestra 1..N ciclos completos de investigação + lance determinístico validado + arbitragem epistêmica,
        sem qualquer limite artificial de 3 lances (suporta 4, 10, 20+ lances contínuos até xeque-mate,
        passes consecutivos no Go, pausa do usuário ou limite configurável de orçamento).
        """
        cache_key = f"{session_id}:{idempotency_key}" if idempotency_key else None
        if cache_key and cache_key in self.advance_idempotency_cache:
            return AdvanceSessionResponse(**self.advance_idempotency_cache[cache_key])

        sess = self.sessions.get(session_id)
        if not sess:
            raise KeyError(f"Sessão {session_id} não encontrada.")

        if sess["status"] == "PAUSED":
            raise SessionStateConflictError("SESSION_PAUSED: A sessão está pausada. Acione /resume para continuar.")
        if sess["status"] == "CANCELLED":
            raise SessionStateConflictError("SESSION_CANCELLED: A sessão foi cancelada.")
        if sess["status"] in ("COMPLETED", "FINISHED") or sess["board"].get("is_game_over"):
            raise SessionStateConflictError("SESSION_COMPLETED: A partida já atingiu condição formal de término.")
        if sess["status"] == "BUDGET_EXHAUSTED":
            raise BudgetExceededError("BUDGET_EXHAUSTED: O orçamento de etapas da sessão foi atingido.")

        if sess["version"] != req.expected_version:
            raise ConcurrencyConflictError(
                f"Conflito de concorrência: versão esperada {req.expected_version}, versão atual {sess['version']}."
            )

        # Verifica orçamento antes de iniciar
        if sess["investigation_step_index"] >= sess["max_steps"]:
            sess["status"] = "BUDGET_EXHAUSTED"
            self._append_session_event(
                session_id,
                "SESSION_BUDGET_EXHAUSTED",
                {"completed_steps": sess["investigation_step_index"], "max_steps": sess["max_steps"]},
            )
            raise BudgetExceededError("BUDGET_EXHAUSTED: Limite máximo de etapas investigativas atingido.")

        try:
            self.gemini_adapter.check_budget(sess["budget"])
        except BudgetExceededError:
            sess["status"] = "BUDGET_EXHAUSTED"
            self._append_session_event(
                session_id,
                "SESSION_BUDGET_EXHAUSTED",
                {"completed_steps": sess["investigation_step_index"], "budget": sess["budget"]},
            )
            raise

        norm_policy = sess["normalized_source_policy"]
        trace_id = f"trc_{uuid.uuid4().hex[:12]}"
        executed_actions: List[Dict[str, Any]] = []
        last_usage = ProviderUsageSchema(
            source="demo_offline" if sess["execution_mode"] == "DEMO_OFFLINE" else "unmeasured"
        ).model_dump()
        latest_claim_dict: Optional[Dict[str, Any]] = None
        latest_judgment_dict: Optional[Dict[str, Any]] = None
        latest_message_dict: Optional[Dict[str, Any]] = None

        # 1. Recuperação de fontes conforme política (OWN_ONLY nunca toca WebSearchAdapter)
        if norm_policy in ("WEB_ONLY", "HYBRID"):
            search_query = f"{sess['title']} {req.user_note}".strip() if req.user_note else sess["title"]
            if search_query not in sess["web_queries_executed"] and len(
                [a for a in sess["artifacts"] if a.get("source_type") == "web"]
            ) < 6:
                try:
                    web_records = self.web_search_adapter.search_public_sources(search_query, max_results=3)
                    sess["web_queries_executed"].append(search_query)
                    sess["source_status_override"] = None
                    ingested_urls: List[str] = []
                    for rec in web_records:
                        art = self.vault.ingest_document(
                            session_id=session_id,
                            name=rec["title"],
                            content=rec["content"],
                            mime_type="text/plain",
                            owner_side="public",
                            source_type="web",
                            url=rec["url"],
                            canonical_url=rec["canonical_url"],
                            domain=rec["domain"],
                            retrieved_at=rec["retrieved_at"],
                            accessible=rec["accessible"],
                        )
                        if not any(existing["id"] == art["id"] for existing in sess["artifacts"]):
                            sess["artifacts"].append(art)
                            ingested_urls.append(rec["canonical_url"])
                    if ingested_urls:
                        self._append_session_event(
                            session_id,
                            "WEB_SOURCES_RETRIEVED",
                            {"query": search_query, "count": len(ingested_urls), "urls": ingested_urls},
                        )
                except SSRFBlockedError:
                    raise
                except WebSearchUnavailableError as ws_err:
                    sess["web_search_diagnostic"] = str(ws_err)
                    if norm_policy == "WEB_ONLY":
                        sess["source_status_override"] = "SEARCH_UNAVAILABLE"
                        raise
                    # Em HYBRID, registra aviso transparente e segue apenas com documentos próprios
                    sess["messages"].append(
                        {
                            "id": f"msg_{uuid.uuid4().hex[:8]}",
                            "role": "system",
                            "agent_label": "Adaptador Web",
                            "text": f"Aviso: Busca web indisponível ({ws_err}); prosseguindo apenas com documentos locais do cofre.",
                            "step_index": sess["investigation_step_index"],
                            "ply_index": sess["ply_count"],
                            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        }
                    )

        # 2. Executa até req.max_actions ciclos investigativos
        for _ in range(req.max_actions):
            if sess["board"].get("is_game_over") or sess["investigation_step_index"] >= sess["max_steps"]:
                break

            sess["status"] = "RUNNING"
            step_num = sess["investigation_step_index"] + 1

            if sess["game"] == "chess":
                chess_eng = self.chess_engines[session_id]
                acting_side = chess_eng.turn
                legal_moves = chess_eng.get_legal_moves()
            else:
                go_eng = self.go_engines[session_id]
                acting_side = "black" if go_eng.turn == "B" else "white"
                legal_moves = go_eng.get_legal_moves()

            if not legal_moves:
                sess["board"]["is_game_over"] = True
                break

            # Seleciona fontes acessíveis apenas ao lado atuante e compatíveis com a política
            accessible_arts = self.vault.get_accessible_artifacts_with_content(
                session_id, requesting_side=acting_side
            )
            if norm_policy == "OWN_ONLY":
                active_arts = [a for a in accessible_arts if a.get("source_type", "document") == "document"]
            elif norm_policy == "WEB_ONLY":
                active_arts = [a for a in accessible_arts if a.get("source_type") == "web"]
            else:
                active_arts = accessible_arts

            prev_claims = [c["statement"] for c in sess["claims"][-6:]]
            force_demo_flag = sess["execution_mode"] == "DEMO_OFFLINE"

            try:
                step_data = self.gemini_adapter.call_research_agent(
                    topic=sess["title"],
                    strategy=sess.get("strategy", "queen"),
                    game=sess["game"],
                    turn_number=step_num,
                    budget=sess["budget"],
                    artifacts=active_arts,
                    mode=sess["mode"],
                    to_move=acting_side,
                    legal_moves=legal_moves,
                    previous_claims=prev_claims,
                    user_note=req.user_note,
                    force_demo=force_demo_flag,
                )
            except ProviderUnavailableError as p_err:
                sess["status"] = "PAUSED"
                sess["last_error"] = str(p_err)
                raise

            last_usage = step_data.get("provider_usage") or last_usage
            sess["provider_usage"] = last_usage

            # 3. Verificação literal de citação e arbitragem epistêmica (jamais aprova SUPPORTED sem prova)
            active_by_id = {a["id"]: a for a in active_arts}
            raw_art_id = (step_data.get("artifact_id") or "").strip()
            raw_quote = (step_data.get("quote_text") or "").strip()

            matched_art = active_by_id.get(raw_art_id)
            if not matched_art and raw_quote and active_arts:
                for cand in active_arts:
                    ok_cand, _ = self.vault.find_verified_quote_offset(cand["id"], raw_quote)
                    if ok_cand:
                        matched_art = cand
                        break

            citations: List[CitationSchema] = []
            future_flag = is_future_projection_topic(sess["title"]) or (
                step_data.get("uncertainty_level") == "PROJECTION"
            )

            if len(active_arts) == 0:
                verdict = "HYPOTHESIS"
                uncertainty = "PROJECTION" if future_flag else "UNCERTAIN"
                rationale = "Nenhuma fonte anexada/recuperada; afirmação classificada como hipótese analítica."
                excerpt_ok = False
            elif matched_art:
                verified_q, offset_str = self.vault.find_verified_quote_offset(matched_art["id"], raw_quote)
                if contains_prompt_injection_attempt(matched_art.get("content", "")):
                    verdict = "INSUFFICIENT"
                    uncertainty = "UNCERTAIN"
                    rationale = "Proteção anti-injeção: instruções adversárias detectadas no documento foram neutralizadas como dados inertes."
                    excerpt_ok = False
                elif not raw_quote:
                    verdict = "INSUFFICIENT"
                    uncertainty = "PROJECTION" if future_flag else "UNCERTAIN"
                    rationale = "Fonte disponível não contém trecho aplicável extraído para sustentar esta afirmação."
                    excerpt_ok = False
                elif not verified_q:
                    citations.append(
                        CitationSchema(
                            artifact_id=matched_art["id"],
                            artifact_name=matched_art["name"],
                            artifact_hash=matched_art["sha256"],
                            quote_text=raw_quote,
                            page_or_offset="QUOTE_MISMATCH",
                            quote_verified=False,
                            url=matched_art.get("canonical_url") or matched_art.get("url"),
                            domain=matched_art.get("domain"),
                        )
                    )
                    verdict = "INSUFFICIENT"
                    uncertainty = "UNCERTAIN"
                    rationale = "QUOTE_MISMATCH: O trecho citado pelo agente não corresponde literalmente ao documento."
                    excerpt_ok = False
                else:
                    citations.append(
                        CitationSchema(
                            artifact_id=matched_art["id"],
                            artifact_name=matched_art["name"],
                            artifact_hash=matched_art["sha256"],
                            quote_text=raw_quote,
                            page_or_offset=offset_str or "verificado",
                            quote_verified=True,
                            url=matched_art.get("canonical_url") or matched_art.get("url"),
                            domain=matched_art.get("domain"),
                        )
                    )
                    excerpt_ok = True
                    if future_flag:
                        verdict = "HYPOTHESIS"
                        uncertainty = "PROJECTION"
                        rationale = (
                            f"Trecho contextual verificado em '{matched_art['name']}' ({offset_str}), "
                            f"mas por tratar de projeção futura permanece como hipótese sujeita a incerteza."
                        )
                    else:
                        verdict = "SUPPORTED"
                        uncertainty = "CERTAIN"
                        rationale = f"Trecho literal verificado em '{matched_art['name']}' ({offset_str}) sustenta a alegação."
            else:
                # Havia active_arts, mas raw_art_id era vazio ou inválido
                if raw_quote:
                    # Tentou citar texto que não bate com nenhuma fonte ativa
                    fallback_art = active_arts[0]
                    citations.append(
                        CitationSchema(
                            artifact_id=fallback_art["id"],
                            artifact_name=fallback_art["name"],
                            artifact_hash=fallback_art["sha256"],
                            quote_text=raw_quote,
                            page_or_offset="QUOTE_MISMATCH",
                            quote_verified=False,
                            url=fallback_art.get("canonical_url") or fallback_art.get("url"),
                            domain=fallback_art.get("domain"),
                        )
                    )
                    verdict = "INSUFFICIENT"
                    uncertainty = "UNCERTAIN"
                    rationale = "Citação proposta não foi localizada literalmente nas fontes autorizadas da sessão."
                    excerpt_ok = False
                else:
                    verdict = "HYPOTHESIS" if future_flag else "INSUFFICIENT"
                    uncertainty = "PROJECTION" if future_flag else "UNCERTAIN"
                    rationale = "Nenhum trecho documental aplicável às fontes atuais; afirmação mantida sem suporte factual."
                    excerpt_ok = False

            # 4. Aplicação determinística da jogada no motor de Xadrez ou Go
            proposed_raw = (step_data.get("proposed_move") or "").strip()
            move_adjusted = False
            move_label = ""
            epistemic_note = ""

            if sess["game"] == "chess":
                chess_eng = self.chess_engines[session_id]
                chosen_uci = proposed_raw.lower()
                if chosen_uci not in legal_moves:
                    chosen_uci = legal_moves[0]
                    move_adjusted = True

                req_epistemic = (sess["mode"] == "debate") and chess_eng.is_capture_move(chosen_uci)
                arb_verdict = None
                if req_epistemic:
                    adj = self.gemini_adapter.call_debate_adjudication(
                        topic=sess["title"],
                        claim_statement=step_data.get("statement", ""),
                        citation_quote=raw_quote if excerpt_ok else "",
                        counter_quote=raw_quote if (excerpt_ok and acting_side == "black") else "",
                        budget=sess["budget"],
                        force_demo=force_demo_flag,
                    )
                    arb_verdict = adj["verdict"]
                    if arb_verdict != "REFUTED":
                        non_cap = [m for m in legal_moves if not chess_eng.is_capture_move(m)]
                        if non_cap:
                            epistemic_note = f" (Captura {chosen_uci} bloqueada sem veredito REFUTED; lance posicional {non_cap[0]} aplicado)"
                            chosen_uci = non_cap[0]
                            req_epistemic = False
                            move_adjusted = True

                mv_res = chess_eng.validate_and_apply_move(
                    move_uci=chosen_uci,
                    arbitration_verdict=arb_verdict,
                    require_epistemic_capture=req_epistemic,
                )

                sess["ply_count"] = chess_eng.ply_count
                move_label = mv_res.san or chosen_uci
                sess["board"] = {
                    "game": "chess",
                    "fen": chess_eng.fen,
                    "to_move": chess_eng.turn,
                    "turn": chess_eng.fullmove_number,
                    "ply_count": chess_eng.ply_count,
                    "last_move": chosen_uci if (mv_res.legal and not mv_res.epistemic_blocked) else None,
                    "captured_white": len(
                        [m for m in chess_eng.move_history if m.get("is_capture") and m.get("turn") == "white"]
                    ),
                    "captured_black": len(
                        [m for m in chess_eng.move_history if m.get("is_capture") and m.get("turn") == "black"]
                    ),
                    "is_game_over": chess_eng.is_game_over,
                    "game_result": chess_eng.get_game_result(),
                    "is_check": mv_res.is_check,
                    "diagnostic_reason": mv_res.diagnostic_reason,
                }
                applied_coord = chosen_uci
                move_applied_ok = mv_res.legal and not mv_res.epistemic_blocked
            else:
                go_eng = self.go_engines[session_id]
                chosen_coord = proposed_raw.upper()
                if chosen_coord not in legal_moves:
                    chosen_coord = legal_moves[0]
                    move_adjusted = True

                go_res = go_eng.play_move(chosen_coord)
                if not go_res.legal:
                    chosen_coord = "PASS"
                    go_res = go_eng.play_move("PASS")
                    move_adjusted = True

                sess["ply_count"] = go_eng.ply_count
                move_label = chosen_coord
                sess["board"] = {
                    "game": "go",
                    "stones": go_eng.to_dict()["stones"],
                    "to_move": "black" if go_eng.turn == "B" else "white",
                    "turn": go_eng.ply_count + 1,
                    "ply_count": go_eng.ply_count,
                    "last_move": chosen_coord,
                    "captured_white": go_eng.captured_by_black,
                    "captured_black": go_eng.captured_by_white,
                    "komi": go_eng.komi,
                    "is_game_over": go_eng.is_game_over,
                    "game_result": go_eng.game_result,
                }
                applied_coord = chosen_coord
                move_applied_ok = go_res.legal

            # 5. Incrementa etapa investigativa independentemente do ply_count
            sess["investigation_step_index"] = step_num
            sess["budget"]["current_steps"] = step_num

            agent_name = self._get_agent_display_name(sess["mode"], acting_side)

            claim_obj = ClaimSchema(
                session_id=session_id,
                statement=step_data.get("statement", f"Análise da etapa {step_num}"),
                status=verdict,
                scope=step_data.get("scope") or sess["title"],
                citations=citations,
                author_agent=agent_name,
                binding_coord=applied_coord,
                step_index=step_num,
                ply_index=sess["ply_count"],
                uncertainty_level=uncertainty,
            )
            latest_claim_dict = claim_obj.model_dump()
            sess["claims"].append(latest_claim_dict)

            judgment_obj = JudgmentSchema(
                session_id=session_id,
                claim_id=claim_obj.id,
                verdict=verdict,
                rubric=RubricEvaluation(
                    claim_identity_score=0.95,
                    comparability_score=0.9,
                    provenance_score=1.0 if excerpt_ok else (0.5 if active_arts else 0.0),
                    excerpt_verification=excerpt_ok,
                    support_or_refutation_match=(verdict == "SUPPORTED"),
                    uncertainty_recognized=True,
                    role_conflict_free=True,
                ),
                rationale=rationale + epistemic_note,
                evaluator_agent="Árbitro Epistêmico",
            )
            latest_judgment_dict = judgment_obj.model_dump()
            sess["judgments"].append(latest_judgment_dict)

            latest_message_dict = {
                "id": f"msg_{uuid.uuid4().hex[:8]}",
                "role": acting_side,
                "agent_label": agent_name,
                "statement": claim_obj.statement,
                "commentary": step_data.get("analyst_commentary", ""),
                "next_subgoal": step_data.get("next_subgoal", ""),
                "move": move_label,
                "coord": applied_coord,
                "move_adjusted": move_adjusted,
                "verdict": verdict,
                "rationale": judgment_obj.rationale,
                "citations": [c.model_dump() for c in citations],
                "step_index": step_num,
                "ply_index": sess["ply_count"],
                "execution_mode": sess["execution_mode"],
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            sess["messages"].append(latest_message_dict)

            # 6. Persiste eventos encadeados no EventStore
            self._append_session_event(session_id, "CLAIM_CREATED", latest_claim_dict)
            self._append_session_event(
                session_id,
                "JUDGMENT_ISSUED",
                {
                    "judgment_id": judgment_obj.id,
                    "claim_id": claim_obj.id,
                    "verdict": verdict,
                    "rationale": judgment_obj.rationale,
                },
            )
            if move_applied_ok:
                if sess["game"] == "chess":
                    move_evt = self._append_session_event(
                        session_id,
                        "CHESS_MOVE",
                        {
                            "uci": applied_coord,
                            "san": move_label,
                            "fen": sess["board"]["fen"],
                            "ply_count": sess["ply_count"],
                            "step_index": step_num,
                            "claim_id": claim_obj.id,
                            "verdict": verdict,
                        },
                    )
                else:
                    move_evt = self._append_session_event(
                        session_id,
                        "GO_MOVE",
                        {
                            "coord": applied_coord,
                            "ply_count": sess["ply_count"],
                            "step_index": step_num,
                            "claim_id": claim_obj.id,
                            "verdict": verdict,
                        },
                    )
                move_evt_id = move_evt["event_id"]
            else:
                move_evt_id = ""

            step_evt = self._append_session_event(
                session_id,
                "INVESTIGATION_STEP_COMPLETED",
                {
                    "step_index": step_num,
                    "ply_count": sess["ply_count"],
                    "claim_id": claim_obj.id,
                    "verdict": verdict,
                    "execution_mode": sess["execution_mode"],
                    "trace_id": trace_id,
                },
            )

            executed_actions.append(
                {
                    "step_index": step_num,
                    "ply_count": sess["ply_count"],
                    "actor": acting_side,
                    "agent_label": agent_name,
                    "coord": applied_coord,
                    "move_label": move_label,
                    "move_adjusted": move_adjusted,
                    "claim_id": claim_obj.id,
                    "verdict": verdict,
                    "move_event_id": move_evt_id,
                    "step_event_id": step_evt["event_id"],
                }
            )

        # 7. Atualiza fase pós-ciclo
        if sess["board"].get("is_game_over"):
            sess["status"] = "COMPLETED"
        elif sess["investigation_step_index"] >= sess["max_steps"]:
            sess["status"] = "BUDGET_EXHAUSTED"
        else:
            sess["status"] = "AWAITING_INPUT"

        tiers = self._evaluate_verification_tiers(sess)
        events_total = len(self.event_store.get_events(session_id))

        resp = AdvanceSessionResponse(
            session_id=session_id,
            version=sess["version"],
            phase=sess["status"],
            execution_mode=sess["execution_mode"],
            source_policy=norm_policy,
            game={
                "kind": sess["game"],
                "ply_count": sess["ply_count"],
                "to_move": sess["board"]["to_move"],
                "is_terminal": sess["board"]["is_game_over"],
                "game_result": sess["board"].get("game_result"),
                "fen": sess["board"].get("fen"),
                "stones": sess["board"].get("stones"),
                "last_move": sess["board"].get("last_move"),
            },
            board=BoardPositionSchema(**sess["board"]),
            actions=executed_actions,
            investigation={
                "completed_steps": sess["investigation_step_index"],
                "max_steps": sess["max_steps"],
                "budget_remaining": max(0, sess["max_steps"] - sess["investigation_step_index"]),
                "current_goal": (
                    latest_message_dict.get("next_subgoal")
                    if latest_message_dict
                    else f"Prosseguir investigação sobre '{sess['title']}'"
                ),
                "latest_message": latest_message_dict,
                "claim": latest_claim_dict,
                "judgment": latest_judgment_dict,
            },
            verification_tiers=tiers,
            artifacts_count=len(sess["artifacts"]),
            claims_count=len(sess["claims"]),
            events_count=events_total,
            trace_id=trace_id,
            provider_usage=ProviderUsageSchema(**last_usage),
        )

        if cache_key:
            self.advance_idempotency_cache[cache_key] = resp.model_dump()

        return resp

    @staticmethod
    def _get_agent_display_name(mode: str, side: str) -> str:
        mapping = {
            ("research", "white"): "Pesquisador Principal",
            ("research", "black"): "Revisor Metodológico",
            ("debate", "white"): "Proponente (Lado A)",
            ("debate", "black"): "Contestador (Lado B)",
            ("audit", "white"): "Auditor de Controles",
            ("audit", "black"): "Auditor de Riscos",
        }
        return mapping.get((mode, side), f"Agente ({side})")

    def submit_action(
        self,
        session_id: str,
        expected_version: int,
        action: ActionPayloadSchema,
        idempotency_key: Optional[str] = None,
    ) -> ActionResponseSchema:
        """
        Executa ação determinística direta no motor de jogo com controle de versão otimista e idempotência.
        Mantém compatibilidade integral com AC-01..AC-06, xeque-mate e IMPASSE_DA_VARIANTE.
        """
        if idempotency_key and idempotency_key in self.idempotency_cache:
            cached = self.idempotency_cache[idempotency_key]
            return ActionResponseSchema(**cached)

        sess = self.sessions.get(session_id)
        if not sess:
            raise KeyError(f"Sessão {session_id} não encontrada.")

        if sess["status"] in ("PAUSED", "CANCELLED"):
            raise SessionStateConflictError(f"Ação bloqueada: sessão em estado {sess['status']}.")

        if sess["version"] != expected_version:
            raise ConcurrencyConflictError(
                f"Conflito de concorrência: versão esperada {expected_version}, versão atual {sess['version']}."
            )

        if sess["status"] == "DRAFT":
            sess["status"] = "RUNNING"

        evidence_result = "NOT_APPLICABLE"

        if sess["game"] == "chess":
            engine = self.chess_engines[session_id]
            if action.kind == "resign":
                winner = "0-1" if engine.turn == "white" else "1-0"
                sess["board"]["is_game_over"] = True
                sess["board"]["game_result"] = winner
                sess["status"] = "COMPLETED"
                evt = self._append_session_event(
                    session_id, "CHESS_RESIGN", {"resigned": engine.turn, "game_result": winner}
                )
                return ActionResponseSchema(
                    accepted=True,
                    version=sess["version"],
                    engine_result="RESIGNED",
                    evidence_result=evidence_result,
                    event_id=evt["event_id"],
                    next_to_move=engine.turn,
                    game_result=winner,
                    board=BoardPositionSchema(**sess["board"]),
                )

            move_uci = action.coord or ""
            require_epistemic = (sess["mode"] == "debate") and engine.is_capture_move(move_uci)
            arbitration_verdict = None

            if require_epistemic:
                # Uma captura em debate só é REFUTED se houver evidência verificada de refutação anexada
                ref_quote = ""
                if action.evidence_ids:
                    for eid in action.evidence_ids:
                        try:
                            art = self.vault.get_artifact(eid, requesting_side=engine.turn)
                            ref_quote = art.get("content", "")[:200]
                        except (KeyError, DocumentAccessForbiddenError):
                            pass
                adjudication = self.gemini_adapter.call_debate_adjudication(
                    topic=sess["title"],
                    claim_statement="Alegação sob contestação",
                    citation_quote="Tese alvo",
                    counter_quote=ref_quote,
                    budget=sess["budget"],
                )
                arbitration_verdict = adjudication["verdict"]
                evidence_result = arbitration_verdict

            res = engine.validate_and_apply_move(
                move_uci=move_uci,
                arbitration_verdict=arbitration_verdict,
                require_epistemic_capture=require_epistemic,
            )

            if not res.legal or res.epistemic_blocked:
                engine_status = (
                    "IMPASSE_DA_VARIANTE"
                    if res.is_impasse_variante
                    else ("ILLEGAL" if not res.legal else "EPISTEMIC_BLOCKED")
                )
                if res.is_impasse_variante:
                    sess["status"] = "COMPLETED"
                board_schema = BoardPositionSchema(
                    game="chess",
                    fen=engine.fen,
                    to_move="white" if engine.turn == "white" else "black",
                    turn=engine.fullmove_number,
                    ply_count=engine.ply_count,
                    is_game_over=engine.is_game_over,
                    game_result=engine.get_game_result(),
                    is_check=res.is_check,
                    diagnostic_reason=res.diagnostic_reason,
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
                    error=res.error,
                )

            engine_status = "LEGAL"
            if res.is_checkmate:
                engine_status = "CHECKMATE"
            elif res.is_draw or res.is_stalemate:
                engine_status = "DRAW"

            sess["ply_count"] = engine.ply_count

            if action.claim_id:
                claim_rec = {
                    "id": action.claim_id,
                    "session_id": session_id,
                    "statement": f"Alegação vinculada ao lance {res.san}",
                    "status": "NOT_ASSESSED" if not sess["artifacts"] else "HYPOTHESIS",
                    "scope": "Ação de tabuleiro",
                    "citations": [],
                    "binding_coord": move_uci,
                    "ply_index": sess["ply_count"],
                }
                sess["claims"].append(claim_rec)

            sess["board"] = {
                "game": "chess",
                "fen": res.fen_after,
                "to_move": "white" if engine.turn == "white" else "black",
                "turn": engine.fullmove_number,
                "ply_count": engine.ply_count,
                "last_move": move_uci,
                "captured_white": len(
                    [m for m in engine.move_history if m.get("is_capture") and m.get("turn") == "white"]
                ),
                "captured_black": len(
                    [m for m in engine.move_history if m.get("is_capture") and m.get("turn") == "black"]
                ),
                "is_game_over": engine.is_game_over,
                "game_result": engine.get_game_result(),
                "is_check": res.is_check,
            }
            if engine.is_game_over:
                sess["status"] = "COMPLETED"

            event_record = self.event_store.append_event(
                session_id=session_id,
                expected_version=sess["version"],
                event_type="CHESS_MOVE",
                payload={
                    "uci": move_uci,
                    "san": res.san,
                    "fen": res.fen_after,
                    "ply_count": engine.ply_count,
                    "is_capture": res.is_capture,
                    "engine_result": engine_status,
                    "evidence_result": evidence_result,
                    "claim_id": action.claim_id,
                },
            )

        else:
            go_engine = self.go_engines[session_id]
            if action.kind == "resign":
                go_res = go_engine.resign(go_engine.turn)
                sess["board"]["is_game_over"] = True
                sess["board"]["game_result"] = go_res.game_result
                sess["status"] = "COMPLETED"
                evt = self._append_session_event(
                    session_id, "GO_RESIGN", {"game_result": go_res.game_result}
                )
                return ActionResponseSchema(
                    accepted=True,
                    version=sess["version"],
                    engine_result="RESIGNED",
                    evidence_result=evidence_result,
                    event_id=evt["event_id"],
                    next_to_move="black" if go_engine.turn == "B" else "white",
                    game_result=go_res.game_result,
                    board=BoardPositionSchema(**sess["board"]),
                )

            coord_str = "PASS" if action.kind == "pass" else (action.coord or "PASS")
            go_res = go_engine.play_move(coord_str)

            if not go_res.legal:
                board_schema = BoardPositionSchema(
                    game="go",
                    stones=go_engine.to_dict()["stones"],
                    to_move="black" if go_engine.turn == "B" else "white",
                    turn=len(go_engine.move_history) + 1,
                    ply_count=go_engine.ply_count,
                    is_game_over=go_engine.is_game_over,
                    game_result=go_engine.game_result,
                )
                return ActionResponseSchema(
                    accepted=False,
                    version=sess["version"],
                    engine_result="ILLEGAL",
                    evidence_result="NOT_APPLICABLE",
                    event_id="",
                    next_to_move="black" if go_engine.turn == "B" else "white",
                    board=board_schema,
                    error=go_res.error,
                )

            if go_res.is_capture:
                evidence_result = "SPATIAL_CAPTURE_MAINTAINS_CLAIMS"

            sess["ply_count"] = go_engine.ply_count

            if action.claim_id:
                claim_rec = {
                    "id": action.claim_id,
                    "session_id": session_id,
                    "statement": f"Alegação associada à pedra {coord_str}",
                    "status": "NOT_ASSESSED" if not sess["artifacts"] else "HYPOTHESIS",
                    "scope": "Região Go",
                    "citations": [],
                    "binding_coord": coord_str,
                    "ply_index": sess["ply_count"],
                }
                sess["claims"].append(claim_rec)

            sess["board"] = {
                "game": "go",
                "stones": go_engine.to_dict()["stones"],
                "to_move": "black" if go_engine.turn == "B" else "white",
                "turn": len(go_engine.move_history) + 1,
                "ply_count": go_engine.ply_count,
                "last_move": coord_str,
                "captured_white": go_engine.captured_by_black,
                "captured_black": go_engine.captured_by_white,
                "komi": go_engine.komi,
                "is_game_over": go_engine.is_game_over,
                "game_result": go_engine.game_result,
            }
            if go_engine.is_game_over:
                sess["status"] = "COMPLETED"

            event_record = self.event_store.append_event(
                session_id=session_id,
                expected_version=sess["version"],
                event_type="GO_MOVE",
                payload={
                    "coord": coord_str,
                    "ply_count": go_engine.ply_count,
                    "is_capture": go_res.is_capture,
                    "captured_count": len(go_res.captured_stones),
                    "evidence_result": evidence_result,
                    "claim_id": action.claim_id,
                },
            )

        sess["version"] = event_record["version"]
        sess["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        response = ActionResponseSchema(
            accepted=True,
            version=sess["version"],
            engine_result="LEGAL",
            evidence_result=evidence_result,
            event_id=event_record["event_id"],
            next_to_move=sess["board"]["to_move"],
            game_result=sess["board"].get("game_result"),
            board=BoardPositionSchema(**sess["board"]),
        )

        if idempotency_key:
            self.idempotency_cache[idempotency_key] = response.model_dump()

        return response
