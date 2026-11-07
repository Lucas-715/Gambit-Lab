"""
Event Store & Replay Engine — Gambit Lab Nocturne (R1.0)
Persistência append-only com encadeamento de hash SHA-256 e replay determinístico
(inclusive replay parcial até qualquer sequência `up_to_seq` sem chamadas ao LLM).
(RNF-02, RF-42, RN-31, RN-32, AC-18, AT-09)
"""
import json
import hashlib
import datetime
import copy
from typing import Dict, Any, List, Optional
from packages.game_rules.chess_engine import EpistemicChessEngine
from packages.game_rules.go_engine import GoEngine9x9


def canonical_json(data: Dict[str, Any]) -> str:
    """Serialização canônica determinística para hashing invariante."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_event_hash(payload: Dict[str, Any], prev_hash: str) -> str:
    """Calcula event_hash = SHA256(canonical_json(payload) + prev_hash)."""
    canon = canonical_json(payload)
    hasher = hashlib.sha256()
    hasher.update((canon + prev_hash).encode("utf-8"))
    return hasher.hexdigest()


class ConcurrencyConflictError(Exception):
    """Lançada quando expected_version != current_version (HTTP 409)."""
    pass


class EventStore:
    """
    Repositório de eventos imutáveis com validação de hash e replay determinístico.
    """

    def __init__(self):
        self._events: Dict[str, List[Dict[str, Any]]] = {}

    def get_events(self, session_id: str, after_seq: int = 0) -> List[Dict[str, Any]]:
        events = self._events.get(session_id, [])
        return [evt for evt in events if evt["seq"] > after_seq]

    def get_last_event(self, session_id: str) -> Optional[Dict[str, Any]]:
        events = self._events.get(session_id, [])
        return events[-1] if events else None

    def get_current_version(self, session_id: str) -> int:
        events = self._events.get(session_id, [])
        return 1 if len(events) == 0 else len(events)

    def append_event(
        self,
        session_id: str,
        expected_version: int,
        event_type: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Adiciona um novo evento garantindo integridade e encadeamento criptográfico.
        """
        events = self._events.setdefault(session_id, [])
        current_version = 1 if len(events) == 0 else len(events)

        if expected_version != current_version:
            raise ConcurrencyConflictError(
                f"Conflito de concorrência: versão esperada {expected_version}, versão atual do servidor {current_version}."
            )

        seq = len(events) + 1
        prev_hash = events[-1]["event_hash"] if events else "GENESIS_HASH_GAMBIT_LAB_V2"
        event_hash = compute_event_hash(payload, prev_hash)

        event_record = {
            "event_id": f"evt_{session_id[:8]}_{seq:04d}",
            "session_id": session_id,
            "seq": seq,
            "version": seq,
            "event_type": event_type,
            "prev_hash": prev_hash,
            "event_hash": event_hash,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "payload": copy.deepcopy(payload),
        }

        events.append(event_record)
        return event_record

    def verify_hash_chain(self, session_id: str) -> bool:
        """Verifica a integridade completa da cadeia de hashes de uma sessão."""
        events = self._events.get(session_id, [])
        if not events:
            return True

        prev_hash = "GENESIS_HASH_GAMBIT_LAB_V2"
        for evt in events:
            if evt["prev_hash"] != prev_hash:
                return False
            expected_hash = compute_event_hash(evt["payload"], prev_hash)
            if evt["event_hash"] != expected_hash:
                return False
            prev_hash = evt["event_hash"]
        return True

    def replay_session(
        self,
        session_id: str,
        game_type: str,
        up_to_seq: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Reconstrói determinística e independentemente o estado do tabuleiro e da investigação
        a partir dos eventos persistidos, sem invocar modelos de linguagem (RN-32, AC-18, AT-09).
        """
        all_events = self._events.get(session_id, [])
        if not self.verify_hash_chain(session_id):
            raise ValueError(f"Cadeia de eventos adulterada na sessão {session_id}!")

        events = (
            [e for e in all_events if e["seq"] <= up_to_seq]
            if up_to_seq is not None
            else all_events
        )

        claims_reconstructed: List[Dict[str, Any]] = []
        judgments_reconstructed: List[Dict[str, Any]] = []
        investigation_steps = 0

        if game_type == "chess":
            engine = EpistemicChessEngine()
            for evt in events:
                p = evt["payload"]
                etype = evt["event_type"]
                if etype == "CHESS_MOVE":
                    uci = p.get("uci")
                    if uci:
                        engine.validate_and_apply_move(uci)
                elif etype == "CLAIM_CREATED":
                    claims_reconstructed.append(p.copy())
                elif etype == "JUDGMENT_ISSUED":
                    judgments_reconstructed.append(p.copy())
                    cid = p.get("claim_id")
                    for c in claims_reconstructed:
                        if c.get("id") == cid:
                            c["status"] = p.get("verdict")
                elif etype == "INVESTIGATION_STEP_COMPLETED":
                    investigation_steps += 1
            return {
                "session_id": session_id,
                "events_count": len(events),
                "total_events_count": len(all_events),
                "replayed_up_to_seq": events[-1]["seq"] if events else 0,
                "ply_count": engine.ply_count,
                "investigation_step_index": investigation_steps,
                "board": engine.to_dict(),
                "claims": claims_reconstructed,
                "judgments": judgments_reconstructed,
            }
        else:
            go_engine = GoEngine9x9()
            for evt in events:
                p = evt["payload"]
                etype = evt["event_type"]
                if etype == "GO_MOVE":
                    coord = p.get("coord")
                    if coord:
                        go_engine.play_move(coord)
                elif etype == "CLAIM_CREATED":
                    claims_reconstructed.append(p.copy())
                elif etype == "JUDGMENT_ISSUED":
                    judgments_reconstructed.append(p.copy())
                    cid = p.get("claim_id")
                    for c in claims_reconstructed:
                        if c.get("id") == cid:
                            c["status"] = p.get("verdict")
                elif etype == "INVESTIGATION_STEP_COMPLETED":
                    investigation_steps += 1
            return {
                "session_id": session_id,
                "events_count": len(events),
                "total_events_count": len(all_events),
                "replayed_up_to_seq": events[-1]["seq"] if events else 0,
                "ply_count": go_engine.ply_count,
                "investigation_step_index": investigation_steps,
                "board": go_engine.to_dict(),
                "claims": claims_reconstructed,
                "judgments": judgments_reconstructed,
            }
