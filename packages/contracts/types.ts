/**
 * Gambit Lab 2.0 — Contratos Tipados Centrais (TypeScript)
 * Baseado na Especificação Integral v2.0
 */

export type SessionMode = 'research' | 'debate' | 'audit';
export type GameType = 'chess' | 'go';

export type SessionStatus =
  | 'DRAFT'
  | 'PREPARING'
  | 'LOCKED'
  | 'RUNNING'
  | 'PAUSED'
  | 'FINISHED'
  | 'FAILED_CONTROLLED';

export type SourcePolicy = 'own_only' | 'web_opt_in';

export type ClaimStatus =
  | 'HYPOTHESIS'
  | 'SUPPORTED'
  | 'REFUTED'
  | 'CONTESTED'
  | 'INCONCLUSIVE'
  | 'NOT_COMPARABLE';

export type AdjudicationVerdict =
  | 'SUPPORTED'
  | 'REFUTED'
  | 'INCONCLUSIVE'
  | 'NOT_COMPARABLE'
  | 'SOURCE_INVALID';

export type ChessStrategy = 'queen' | 'king' | 'evans' | 'critical_defense';
export type GoStrategy = 'influence' | 'territory' | 'invasion' | 'connection' | 'balance';
export type StrategyKey = ChessStrategy | GoStrategy;

export interface SessionBudget {
  max_calls: number;
  max_tokens: number;
  current_calls: number;
  current_tokens: number;
}

export interface BoardPosition {
  game: GameType;
  fen?: string;          // For Chess (FEN string)
  grid?: string[][];     // For Go 9x9 (empty, 'B', 'W')
  to_move: 'white' | 'black';
  turn: number;
  captured_white: number;
  captured_black: number;
  komi?: number;
  is_game_over: boolean;
  game_result?: string | null;
}

export interface Artifact {
  id: string;
  session_id: string;
  name: string;
  sha256: string;
  mime_type: string;
  owner_side?: 'white' | 'black' | 'public';
  created_at: string;
  char_count: number;
}

export interface Citation {
  id: string;
  artifact_id: string;
  artifact_name: string;
  artifact_hash: string;
  quote_text: string;
  page_or_offset: string;
  created_at: string;
}

export interface Claim {
  id: string;
  session_id: string;
  branch_id?: string;
  statement: string;
  status: ClaimStatus;
  scope: string;
  citations: Citation[];
  author_agent: string;
  created_at: string;
  binding_coord?: string; // Chess square (e.g. "d4") or Go intersection (e.g. "D4")
}

export interface Judgment {
  id: string;
  session_id: string;
  claim_id: string;
  verdict: AdjudicationVerdict;
  rubric: {
    claim_identity_score: number; // 0-1
    comparability_score: number;
    provenance_score: number;
    excerpt_verification: boolean;
    support_or_refutation_match: boolean;
    uncertainty_recognized: boolean;
    role_conflict_free: boolean;
  };
  rational: string;
  evaluator_agent: string;
  created_at: string;
}

export interface ActionPayload {
  kind: 'move_piece' | 'place_stone' | 'pass' | 'resign';
  coord?: string;           // e.g. "e2e4" or "D4"
  from_coord?: string;      // e.g. "e2"
  to_coord?: string;        // e.g. "e4"
  promotion?: string;       // e.g. "q"
  claim_id?: string;
  evidence_ids?: string[];
  refutation_target_id?: string; // for epistemic capture in debate
}

export interface ActionSubmission {
  expected_version: number;
  action: ActionPayload;
}

export interface ActionResponse {
  accepted: boolean;
  version: number;
  engine_result: 'LEGAL' | 'ILLEGAL' | 'CHECKMATE' | 'DRAW' | 'IMPASSE_DA_VARIANTE';
  evidence_result?: AdjudicationVerdict | 'NOT_APPLICABLE';
  event_id: string;
  next_to_move: 'white' | 'black';
  game_result?: string | null;
  board: BoardPosition;
  error?: string;
}

export interface SessionEvent {
  event_id: string;
  session_id: string;
  seq: number;
  version: number;
  event_type: string;
  prev_hash: string;
  event_hash: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

export interface FusionBranch {
  branch_id: string;
  preset: StrategyKey;
  game: GameType;
  title: string;
  focus: string;
  board: BoardPosition;
  claims: Claim[];
}

export interface DivergenceItem {
  topic: string;
  classification: 'CONVERGENT' | 'CONTRADICTORY' | 'DIFFERENT_SCOPE' | 'INSUFFICIENT';
  details: string;
  branch_claims: { branch_id: string; statement: string; quote: string }[];
}

export interface FusionSynthesisReport {
  session_id: string;
  question: string;
  mode: SessionMode;
  branches: { branch_id: string; preset: string; summary: string }[];
  deduplicated_sources_count: number;
  divergences: DivergenceItem[];
  unified_synthesis: string;
  evidence_level: 'HIGH' | 'MODERATE' | 'LOW' | 'INCONCLUSIVE';
  limitations: string[];
  created_at: string;
}

export interface SessionState {
  id: string;
  title: string;
  mode: SessionMode;
  game: GameType;
  status: SessionStatus;
  version: number;
  source_policy: SourcePolicy;
  budget: SessionBudget;
  board: BoardPosition;
  active_branch_id?: string;
  branches?: FusionBranch[];
  claims: Claim[];
  artifacts: Artifact[];
  created_at: string;
  updated_at: string;
}
