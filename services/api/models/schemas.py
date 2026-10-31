"""
Pydantic Schemas — Gambit Lab 2.0 (Nocturne R1.0)
Definição estrita de contratos de dados para API, Event Store, Capabilities e Agentes.
Inclui distinção rigorosa de três camadas epistêmicas:
1. Integridade (SHA-256 e Event Store)
2. Verificação de Fonte (Quote literal e Localizador)
3. Avaliação Epistêmica (Sustentação/Refutação/Incerteza da Alegação)
"""
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
import uuid
import datetime

SessionMode = Literal["research", "debate", "audit"]
GameType = Literal["chess", "go"]
SessionStatus = Literal[
    "DRAFT",
    "PREPARING",
    "READY",
    "LOCKED",
    "RUNNING",
    "AWAITING_INPUT",
    "PAUSED",
    "BUDGET_EXHAUSTED",
    "COMPLETED",
    "FINISHED",
    "FAILED",
    "FAILED_CONTROLLED",
    "CANCELLED",
]
SourcePolicy = Literal["OWN_ONLY", "WEB_ONLY", "HYBRID", "own_only", "web_opt_in"]
NormalizedSourcePolicy = Literal["OWN_ONLY", "WEB_ONLY", "HYBRID"]
ExecutionMode = Literal["DEMO_OFFLINE", "LIVE_DOCUMENTS", "LIVE_WEB", "LIVE_HYBRID"]

# Três níveis formais e separados de verificação (AUD-03 / Problema 1)
IntegrityStatus = Literal[
    "INTEGRITY_VERIFIED", "INTEGRITY_COMPROMISED", "NOT_CALCULATED", "NOT_ASSESSED"
]
SourceStatus = Literal[
    "SOURCE_VERIFIED",
    "SOURCE_UNRESOLVED",
    "QUOTE_MISMATCH",
    "NO_SOURCES_ATTACHED",
    "NOT_ASSESSED",
    "SEARCH_UNAVAILABLE",
]
EvidenceVerdict = Literal[
    "SUPPORTED",
    "REFUTED",
    "INSUFFICIENT",
    "INCONCLUSIVE",
    "NOT_COMPARABLE",
    "HYPOTHESIS",
    "NOT_ASSESSED",
]
ClaimStatus = Literal[
    "HYPOTHESIS",
    "SUPPORTED",
    "REFUTED",
    "CONTESTED",
    "INSUFFICIENT",
    "INCONCLUSIVE",
    "NOT_COMPARABLE",
    "NOT_ASSESSED",
]


def normalize_source_policy(policy: str) -> NormalizedSourcePolicy:
    """Normaliza políticas legadas e atuais para OWN_ONLY | WEB_ONLY | HYBRID."""
    p = (policy or "OWN_ONLY").strip().upper()
    if p in ("OWN_ONLY",):
        return "OWN_ONLY"
    if p in ("WEB_ONLY",):
        return "WEB_ONLY"
    if p in ("HYBRID", "WEB_OPT_IN"):
        return "HYBRID"
    return "OWN_ONLY"


class SessionBudget(BaseModel):
    max_calls: int = 24
    max_tokens: int = 120000
    max_steps: int = 12
    current_calls: int = 0
    current_tokens: int = 0
    current_steps: int = 0
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    last_latency_ms: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    usage_measured: bool = False


class CreateSessionRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    mode: SessionMode = "research"
    game: GameType = "chess"
    source_policy: SourcePolicy = "OWN_ONLY"
    budget: Optional[SessionBudget] = None
    initial_strategy: Optional[str] = "queen"
    max_steps: int = Field(default=12, ge=1, le=60)
    force_demo: Optional[bool] = None
    use_demo_fixture: Optional[bool] = None


class BoardPositionSchema(BaseModel):
    game: GameType
    fen: Optional[str] = None
    stones: Optional[List[Dict[str, Any]]] = None
    to_move: Literal["white", "black"]
    turn: int = 1
    ply_count: int = 0
    last_move: Optional[str] = None
    captured_white: int = 0
    captured_black: int = 0
    komi: Optional[float] = 6.5
    is_game_over: bool = False
    game_result: Optional[str] = None
    is_check: bool = False
    diagnostic_reason: Optional[str] = None


class ArtifactSchema(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    name: str
    sha256: str
    mime_type: str = "text/plain"
    owner_side: Literal["white", "black", "public"] = "public"
    source_type: Literal["document", "web"] = "document"
    url: Optional[str] = None
    canonical_url: Optional[str] = None
    domain: Optional[str] = None
    retrieved_at: Optional[str] = None
    accessible: bool = True
    created_at: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    char_count: int = 0
    content_preview: Optional[str] = None


class CitationSchema(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    artifact_id: str
    artifact_name: str
    artifact_hash: str
    quote_text: str
    page_or_offset: str = "p.1"
    quote_verified: bool = False
    url: Optional[str] = None
    domain: Optional[str] = None
    created_at: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


class ClaimSchema(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    branch_id: Optional[str] = None
    statement: str
    status: ClaimStatus = "NOT_ASSESSED"
    scope: str = "Geral"
    citations: List[CitationSchema] = Field(default_factory=list)
    author_agent: str = "agent_pesquisador"
    created_at: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    binding_coord: Optional[str] = None
    step_index: Optional[int] = None
    ply_index: Optional[int] = None
    uncertainty_level: Literal["CERTAIN", "PROJECTION", "UNCERTAIN"] = "UNCERTAIN"


class RubricEvaluation(BaseModel):
    claim_identity_score: float = 1.0
    comparability_score: float = 1.0
    provenance_score: float = 1.0
    excerpt_verification: bool = False
    support_or_refutation_match: bool = False
    uncertainty_recognized: bool = True
    role_conflict_free: bool = True


class JudgmentSchema(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    claim_id: str
    verdict: EvidenceVerdict
    rubric: RubricEvaluation
    rationale: str
    evaluator_agent: str = "agent_arbitro"
    created_at: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


class ActionPayloadSchema(BaseModel):
    kind: Literal["move_piece", "place_stone", "pass", "resign"]
    coord: Optional[str] = None  # e.g. "e2e4" ou "D4"
    claim_id: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)
    refutation_target_id: Optional[str] = None


class SubmitActionRequest(BaseModel):
    expected_version: int
    action: ActionPayloadSchema


class ActionResponseSchema(BaseModel):
    accepted: bool
    version: int
    engine_result: str
    evidence_result: Optional[str] = None
    event_id: str
    next_to_move: Literal["white", "black"]
    game_result: Optional[str] = None
    board: BoardPositionSchema
    error: Optional[str] = None


class ProviderUsageSchema(BaseModel):
    source: Literal["gemini_api", "demo_offline", "unmeasured"] = "unmeasured"
    model: Optional[str] = None
    tokens: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    estimated_cost_usd: Optional[float] = None


class AdvanceSessionRequest(BaseModel):
    expected_version: int
    intent: Literal["CONTINUE_INVESTIGATION"] = "CONTINUE_INVESTIGATION"
    max_actions: int = Field(default=1, ge=1, le=5)
    user_note: Optional[str] = Field(default=None, max_length=500)


class AdvanceSessionResponse(BaseModel):
    session_id: str
    version: int
    phase: SessionStatus
    execution_mode: ExecutionMode
    source_policy: NormalizedSourcePolicy
    game: Dict[str, Any]
    board: BoardPositionSchema
    actions: List[Dict[str, Any]]
    investigation: Dict[str, Any]
    verification_tiers: Dict[str, Any]
    artifacts_count: int
    claims_count: int
    events_count: int
    trace_id: str
    provider_usage: ProviderUsageSchema


class CapabilitiesResponseSchema(BaseModel):
    app: str = "Gambit Lab Nocturne"
    version: str = "2.1.0-nocturne"
    gemini: Dict[str, Any]
    web_search: Dict[str, Any]
    supported_policies: List[NormalizedSourcePolicy] = ["OWN_ONLY", "WEB_ONLY", "HYBRID"]
    supported_execution_modes: List[ExecutionMode] = [
        "DEMO_OFFLINE",
        "LIVE_DOCUMENTS",
        "LIVE_WEB",
        "LIVE_HYBRID",
    ]
    supported_games: List[GameType] = ["chess", "go"]
    supported_modes: List[SessionMode] = ["research", "debate", "audit"]
    default_max_steps: int = 12


class SessionEventSchema(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    seq: int
    version: int
    event_type: str
    prev_hash: str
    event_hash: str
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    payload: Dict[str, Any]


class FusionBranchSchema(BaseModel):
    branch_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    preset: str
    game: GameType
    title: str
    focus: str
    board: BoardPositionSchema
    claims: List[ClaimSchema] = Field(default_factory=list)


class DivergenceItemSchema(BaseModel):
    topic: str
    classification: Literal["CONVERGENT", "CONTRADICTORY", "DIFFERENT_SCOPE", "INSUFFICIENT"]
    details: str
    branch_claims: List[Dict[str, Any]] = Field(default_factory=list)


class FusionSynthesisReportSchema(BaseModel):
    session_id: str
    question: str
    mode: SessionMode
    branches: List[Dict[str, Any]]
    deduplicated_sources_count: int
    divergences: List[DivergenceItemSchema]
    unified_synthesis: str
    evidence_level: Literal["HIGH", "MODERATE", "LOW", "INCONCLUSIVE"]
    limitations: List[str]
    created_at: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


class SessionResponseSchema(BaseModel):
    id: str
    title: str
    mode: SessionMode
    game: GameType
    status: SessionStatus
    execution_mode: ExecutionMode = "DEMO_OFFLINE"
    version: int
    source_policy: str
    normalized_source_policy: NormalizedSourcePolicy = "OWN_ONLY"
    ply_count: int = 0
    investigation_step_index: int = 0
    max_steps: int = 12
    budget: SessionBudget
    board: BoardPositionSchema
    active_branch_id: Optional[str] = None
    branches: List[FusionBranchSchema] = Field(default_factory=list)
    claims: List[ClaimSchema] = Field(default_factory=list)
    artifacts: List[ArtifactSchema] = Field(default_factory=list)
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    judgments: List[Dict[str, Any]] = Field(default_factory=list)
    integrity_status: IntegrityStatus = "NOT_CALCULATED"
    source_status: SourceStatus = "NO_SOURCES_ATTACHED"
    evidence_assessment: EvidenceVerdict = "HYPOTHESIS"
    diagnostic_reason: Optional[str] = None
    provider_usage: ProviderUsageSchema = Field(default_factory=ProviderUsageSchema)
    created_at: str
    updated_at: str
