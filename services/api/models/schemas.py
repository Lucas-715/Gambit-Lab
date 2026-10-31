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
    "UNVERIFIED",
    "SOURCE_VERIFIED",
    "EVIDENCE_REVIEWED",
    "SUPPORTED",
    "REFUTED",
    "INSUFFICIENT",
    "INCONCLUSIVE",
    "NOT_COMPARABLE",
    "HYPOTHESIS",
    "NOT_ASSESSED",
]
ClaimStatus = Literal[
    "UNVERIFIED",
    "SOURCE_VERIFIED",
    "EVIDENCE_REVIEWED",
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
    depth: Literal["quick", "standard", "deep"] = "standard"
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


MatchDepth = Literal["quick", "standard", "deep"]
TerminationCriterion = Literal["BOARD_VICTORY", "DRAW_BY_RULE", "BUDGET_EXHAUSTED"]
LudicResult = Literal["WHITE_WINS", "BLACK_WINS", "DRAW", "UNDECIDED"]
EpistemicResult = Literal[
    "PRO_THESIS_SUPPORTED",
    "CONTRA_THESIS_SUPPORTED",
    "INCONCLUSIVE",
    "OPEN_HYPOTHESIS",
]


class PieceArtifactRefSchema(BaseModel):
    artifact_id: str
    title: str
    sha256: str
    owner_side: Literal["white", "black", "public"] = "public"
    source_type: Literal["document", "web"] = "document"
    url: Optional[str] = None
    domain: Optional[str] = None
    quote_text: Optional[str] = None
    verified: bool = False
    played_at_ply: Optional[int] = None


class PieceHistoryEntrySchema(BaseModel):
    ply: int
    move_label: str
    from_coord: Optional[str] = None
    to_coord: Optional[str] = None
    event_kind: Literal[
        "DEPLOYED",
        "ADVANCE",
        "CONFRONTATION_WON",
        "CONFRONTATION_BLOCKED",
        "CAPTURED",
        "PIECE_CAPTURED",
        "STONES_CAPTURED",
        "TERRITORY_PRESSURE",
    ] = "ADVANCE"
    summary: str
    arbiter_verdict: Optional[str] = None


class PieceDossierSchema(BaseModel):
    piece_id: str
    side: Literal["pro", "contra"]
    color: Literal["white", "black"]
    piece_type: str
    symbol: str
    label: str
    role: str
    initial_coord: str
    current_coord: Optional[str] = None
    stones: List[str] = Field(default_factory=list)
    alive: bool = True
    captured_at_ply: Optional[int] = None
    captured_by_piece_id: Optional[str] = None
    fall_explanation: Optional[str] = None
    claim: str
    supporting_artifacts: List[PieceArtifactRefSchema] = Field(default_factory=list)
    counter_artifacts: List[PieceArtifactRefSchema] = Field(default_factory=list)
    confidence_score: float = 0.0
    epistemic_status: EvidenceVerdict = "HYPOTHESIS"
    history: List[PieceHistoryEntrySchema] = Field(default_factory=list)


class MoveAuditPayloadSchema(BaseModel):
    session_id: str
    ply: int
    game: GameType
    move: Dict[str, Any]
    piece: Dict[str, Any]
    opponent: Optional[Dict[str, Any]] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)
    argument_verdict: Dict[str, Any] = Field(default_factory=dict)
    board_outcome: Dict[str, Any] = Field(default_factory=dict)
    event_seq: Optional[int] = None
    event_hash: Optional[str] = None
    move_event_seq: Optional[int] = None
    control_audit: Optional[Dict[str, Any]] = None


class MatchPlyRecordSchema(BaseModel):
    ply: int
    event_seq: int
    move_event_seq: Optional[int] = None
    side: Literal["pro", "contra"]
    color: Literal["white", "black"]
    move: str
    san: str
    from_coord: Optional[str] = None
    to_coord: Optional[str] = None
    piece_id: str
    piece_label: str
    piece_role: str
    claim_statement: str
    quote_text: Optional[str] = None
    artifact_title: Optional[str] = None
    artifact_id: Optional[str] = None
    epistemic_verdict: EvidenceVerdict = "HYPOTHESIS"
    is_capture: bool = False
    epistemic_blocked: bool = False
    captured_piece_id: Optional[str] = None
    captured_piece_label: Optional[str] = None
    confrontation_summary: Optional[str] = None
    is_turning_point: bool = False
    pro_momentum: float = 0.5
    board_snapshot: BoardPositionSchema
    audit_payload: Optional[MoveAuditPayloadSchema] = None
    control_audit: Optional[Dict[str, Any]] = None
    piece_coords_snapshot: Dict[str, Optional[str]] = Field(default_factory=dict)
    piece_stones_snapshot: Dict[str, List[str]] = Field(default_factory=dict)


class MatchStageInfoSchema(BaseModel):
    index: int
    key: str
    label: str
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    detail: Optional[str] = None


class MatchConclusionSchema(BaseModel):
    termination_criterion: TerminationCriterion
    termination_reason: str
    ludic_result: LudicResult
    ludic_score_label: str
    winner_side: Literal["pro", "contra", "draw", "none"]
    epistemic_result: EpistemicResult
    epistemic_verdict_label: str
    pro_thesis: str
    contra_thesis: str
    pro_epistemic_score: float
    contra_epistemic_score: float
    verified_sources_pro: int
    verified_sources_contra: int
    turning_point_ply: Optional[int] = None
    turning_point_summary: Optional[str] = None
    is_provisional: bool = False
    final_synthesis: str
    key_arguments_pro: List[str] = Field(default_factory=list)
    key_arguments_contra: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class ResearchMatchStateSchema(BaseModel):
    session_id: str
    status: Literal["NOT_STARTED", "IN_PROGRESS", "COMPLETED", "BUDGET_EXHAUSTED"] = "NOT_STARTED"
    depth: MatchDepth = "standard"
    execution_mode: str = "DEMO_OFFLINE"
    plies_budget: int = 160
    plies_played: int = 0
    game_finished: bool = False
    resumable: bool = False
    pro_color: Literal["white", "black"] = "white"
    contra_color: Literal["white", "black"] = "black"
    pro_thesis: str = ""
    contra_thesis: str = ""
    current_stage: int = 0
    percent_complete: int = 0
    is_complete: bool = False
    stages: List[MatchStageInfoSchema] = Field(default_factory=list)
    pieces: List[PieceDossierSchema] = Field(default_factory=list)
    timeline: List[MatchPlyRecordSchema] = Field(default_factory=list)
    conclusion: Optional[MatchConclusionSchema] = None


class RunMatchRequest(BaseModel):
    depth: Optional[MatchDepth] = None


class ResumeMatchRequest(BaseModel):
    extra_plies: Optional[int] = Field(default=None, ge=2, le=400)


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
    depth: MatchDepth = "standard"
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
    research_match: Optional[ResearchMatchStateSchema] = None
    integrity_status: IntegrityStatus = "NOT_CALCULATED"
    source_status: SourceStatus = "NO_SOURCES_ATTACHED"
    evidence_assessment: EvidenceVerdict = "HYPOTHESIS"
    diagnostic_reason: Optional[str] = None
    provider_usage: ProviderUsageSchema = Field(default_factory=ProviderUsageSchema)
    created_at: str
    updated_at: str
