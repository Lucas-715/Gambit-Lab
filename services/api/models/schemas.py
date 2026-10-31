"""
Pydantic Schemas — Gambit Lab 2.0
Definição estrita de contratos de dados para API, Event Store e Agentes.
Inclui distinção rigorosa de três camadas:
1. Integridade (SHA-256 e Event Store)
2. Verificação de Fonte (Quote e Localizador)
3. Avaliação Epistêmica (Sustentação/Refutação da Alegação)
"""
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
import uuid
import datetime

SessionMode = Literal["research", "debate", "audit"]
GameType = Literal["chess", "go"]
SessionStatus = Literal[
    "DRAFT", "PREPARING", "LOCKED", "RUNNING", "PAUSED", "FINISHED", "FAILED_CONTROLLED"
]
SourcePolicy = Literal["own_only", "web_opt_in"]

# Três níveis formais e separados de verificação (Problema 1 da Auditoria)
IntegrityStatus = Literal["INTEGRITY_VERIFIED", "INTEGRITY_COMPROMISED", "NOT_CALCULATED"]
SourceStatus = Literal["SOURCE_VERIFIED", "SOURCE_UNRESOLVED", "QUOTE_MISMATCH", "NO_SOURCES_ATTACHED"]
EvidenceVerdict = Literal["SUPPORTED", "REFUTED", "INSUFFICIENT", "NOT_COMPARABLE", "HYPOTHESIS"]
ClaimStatus = Literal["HYPOTHESIS", "SUPPORTED", "REFUTED", "CONTESTED", "INSUFFICIENT", "NOT_COMPARABLE"]


class SessionBudget(BaseModel):
    max_calls: int = 15
    max_tokens: int = 50000
    current_calls: int = 0
    current_tokens: int = 0


class CreateSessionRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    mode: SessionMode = "research"
    game: GameType = "chess"
    source_policy: SourcePolicy = "own_only"
    budget: Optional[SessionBudget] = None
    initial_strategy: Optional[str] = "queen"


class BoardPositionSchema(BaseModel):
    game: GameType
    fen: Optional[str] = None
    stones: Optional[List[Dict[str, Any]]] = None
    to_move: Literal["white", "black"]
    turn: int = 1
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
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
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
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class ClaimSchema(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    branch_id: Optional[str] = None
    statement: str
    status: ClaimStatus = "HYPOTHESIS"
    scope: str = "Geral"
    citations: List[CitationSchema] = Field(default_factory=list)
    author_agent: str = "agent_pesquisador"
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    binding_coord: Optional[str] = None
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
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class ActionPayloadSchema(BaseModel):
    kind: Literal["move_piece", "place_stone", "pass", "resign"]
    coord: Optional[str] = None          # e.g. "e2e4" ou "D4"
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


class SessionEventSchema(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    seq: int
    version: int
    event_type: str
    prev_hash: str
    event_hash: str
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
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
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class SessionResponseSchema(BaseModel):
    id: str
    title: str
    mode: SessionMode
    game: GameType
    status: SessionStatus
    version: int
    source_policy: SourcePolicy
    budget: SessionBudget
    board: BoardPositionSchema
    active_branch_id: Optional[str] = None
    branches: List[FusionBranchSchema] = Field(default_factory=list)
    claims: List[ClaimSchema] = Field(default_factory=list)
    artifacts: List[ArtifactSchema] = Field(default_factory=list)
    integrity_status: IntegrityStatus = "NOT_CALCULATED"
    source_status: SourceStatus = "NO_SOURCES_ATTACHED"
    evidence_assessment: EvidenceVerdict = "HYPOTHESIS"
    diagnostic_reason: Optional[str] = None
    created_at: str
    updated_at: str
