"""
Registro canônico de cada lance no Event Store, claims, julgamentos e mensagens da conversa.
"""
import datetime
import uuid
from typing import Any, Dict, List, Optional

from services.api.agents.gemini_adapter import is_future_projection_topic
from services.api.models.schemas import (
    CitationSchema,
    ClaimSchema,
    JudgmentSchema,
    RubricEvaluation,
)


class RecordingMixin:
    def _record_ply_claim_and_event(
        self,
        sess: Dict[str, Any],
        ply_idx: int,
        acting_side: str,
        acting_color: str,
        move_raw: str,
        san_label: str,
        piece_doc: Optional[Dict[str, Any]],
        confrontation_note: Optional[str],
    ) -> Any:
        session_id = sess["id"]
        citations: List[CitationSchema] = []
        verdict = "HYPOTHESIS"
        if piece_doc and piece_doc.get("supporting_artifacts"):
            aref = piece_doc["supporting_artifacts"][0]
            if aref.get("verified") and aref.get("quote_text"):
                ok, offset_str = self.sm.vault.find_verified_quote_offset(
                    aref["artifact_id"], aref["quote_text"]
                )
                if ok:
                    citations.append(
                        CitationSchema(
                            artifact_id=aref["artifact_id"],
                            artifact_name=aref["title"],
                            artifact_hash=aref["sha256"],
                            quote_text=aref["quote_text"],
                            page_or_offset=offset_str or "verified",
                            quote_verified=True,
                            url=aref.get("url"),
                            domain=aref.get("domain"),
                        )
                    )
                    # v2.3 C01: Citação verificada no documento = SOURCE_VERIFIED
                    verdict = "SOURCE_VERIFIED"

        stmt = (
            f"[{piece_doc['label']}] {piece_doc['claim']}"
            if piece_doc
            else f"Lance #{ply_idx}: {san_label}"
        )
        if confrontation_note:
            stmt = f"{stmt} — {confrontation_note}"

        uncertainty = "PROJECTION" if is_future_projection_topic(sess["title"]) else ("CERTAIN" if verdict == "SUPPORTED" else "UNCERTAIN")
        claim = ClaimSchema(
            session_id=session_id,
            statement=stmt[:600],
            status=verdict,
            scope=piece_doc["role"] if piece_doc else "Partida Completa",
            citations=citations,
            author_agent=f"agent_{acting_side}_{acting_color}",
            binding_coord=move_raw,
            step_index=ply_idx,
            ply_index=ply_idx,
            uncertainty_level=uncertainty,
        )
        claim_dict = claim.model_dump()
        sess["claims"].append(claim_dict)

        judgment = JudgmentSchema(
            session_id=session_id,
            claim_id=claim.id,
            verdict=verdict,
            rubric=RubricEvaluation(
                claim_identity_score=1.0,
                comparability_score=0.92 if verdict == "SUPPORTED" else 0.7,
                provenance_score=1.0 if verdict == "SUPPORTED" else 0.45,
                excerpt_verification=(verdict == "SUPPORTED"),
                support_or_refutation_match=(verdict == "SUPPORTED"),
                uncertainty_recognized=True,
                role_conflict_free=True,
            ),
            rationale=confrontation_note or (
                "Citação literal verificada no cofre isolado da peça."
                if verdict == "SUPPORTED"
                else "Subtese registrada sem citação literal decisiva; mantida como hipótese."
            ),
        )
        judgment_dict = judgment.model_dump()
        sess["judgments"].append(judgment_dict)

        sess["messages"].append(
            {
                "id": f"msg_{uuid.uuid4().hex[:8]}",
                "role": acting_color,
                "agent_label": piece_doc["label"] if piece_doc else f"Lado {acting_side.upper()}",
                "agent": piece_doc["label"] if piece_doc else f"Lado {acting_side.upper()}",
                "side": acting_color,
                "thesis_side": acting_side,
                "move": san_label,
                "coord": move_raw,
                "statement": claim.statement,
                "commentary": confrontation_note or (piece_doc["role"] if piece_doc else ""),
                "verdict": verdict,
                "rationale": judgment.rationale,
                "citations": [c.model_dump() for c in citations],
                "quote_text": citations[0].quote_text if citations else "",
                "artifact_name": piece_doc["supporting_artifacts"][0]["title"] if (piece_doc and piece_doc.get("supporting_artifacts")) else "",
                "step_index": ply_idx,
                "ply_index": ply_idx,
                "execution_mode": sess["execution_mode"],
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
        )

        # Persiste eventos canônicos compatíveis com EventStore.replay_session(up_to_seq=...)!
        if sess["game"] == "chess":
            move_evt = self.sm._append_session_event(
                session_id,
                "CHESS_MOVE",
                {
                    "uci": move_raw,
                    "san": san_label,
                    "side": acting_color,
                    "thesis_side": acting_side,
                    "piece_id": piece_doc["piece_id"] if piece_doc else None,
                    "ply_count": ply_idx,
                },
            )
        else:
            move_evt = self.sm._append_session_event(
                session_id,
                "GO_MOVE",
                {
                    "coord": move_raw,
                    "side": acting_color,
                    "thesis_side": acting_side,
                    "piece_id": piece_doc["piece_id"] if piece_doc else None,
                    "ply_count": ply_idx,
                },
            )
        self.sm._append_session_event(session_id, "CLAIM_CREATED", claim_dict)
        self.sm._append_session_event(session_id, "JUDGMENT_ISSUED", judgment_dict)
        step_evt = self.sm._append_session_event(
            session_id,
            "INVESTIGATION_STEP_COMPLETED",
            {
                "step_index": ply_idx,
                "ply_count": ply_idx,
                "move": move_raw,
                "san": san_label,
                "piece_id": piece_doc["piece_id"] if piece_doc else None,
                "verdict": verdict,
            },
        )
        return {
            "seq": step_evt["seq"],
            "hash": step_evt.get("hash") or step_evt.get("event_hash"),
            "move_seq": move_evt["seq"],
            "move_hash": move_evt.get("hash") or move_evt.get("event_hash"),
        }
