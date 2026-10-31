"""
Event Store & Replay Engine — Gambit Lab 2.0
Persistência append-only com encadeamento de hash SHA-256 e replay determinístico.
(RNF-02, RF-42, RN-31, RN-32, AC-18)
"""
import json
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from packages.game_rules.chess_engine import EpistemicChessEngine
from packages.game_rules.go_engine import GoEngine9x9


def canonical_json(data: Dict[str, Any]) -> str:
    """Serialização canônica determinística para hashing invariante."""
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def compute_event_hash(payload: Dict[str, Any], prev_hash: str) -> str:
    """Calcula event_hash = SHA256(canonical_json(payload) + prev_hash)."""
    canon = canonical_json(payload)
    hasher = hashlib.sha256()
    hasher.update((canon + prev_hash).encode('utf-8'))
    return hasher.hexdigest()


class ConcurrencyConflictError(Exception):
    """Lançada quando expected_version != current_version (HTTP 409)."""
    pass


class EventStore:
    """
    Repositório de eventos imutáveis com validação de hash e replay.
    """

    def __init__(self):
        # session_id -> List of events
        self._events: Dict[str, List[Dict[str, Any]]] = {}

    def get_events(self, session_id: str, after_seq: int = 0) -> List[Dict[str, Any]]:
        events = self._events.get(session_id, [])
        return [evt for evt in events if evt["seq"] > after_seq]

    def get_last_event(self, session_id: str) -> Optional[Dict[str, Any]]:
        events = self._events.get(session_id, [])
        return events[-1] if events else None

    def append_event(
        self,
        session_id: str,
        expected_version: int,
        event_type: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Adiciona um novo evento garantindo integridade e encadeamento criptográfico.
        Para o evento gênese (SESSION_CREATED): expected_version == 1.
        Para os eventos subsequentes: expected_version == len(events), onde len(events)
        corresponde à versão atual da sessão apresentada ao cliente.
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
            "payload": payload
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

    def replay_session(self, session_id: str, game_type: str) -> Dict[str, Any]:
        """
        Reconstrói determinística e independentemente o estado do tabuleiro a partir dos eventos,
        sem invocar modelos de linguagem (RN-32, AC-18).
        """
        events = self._events.get(session_id, [])
        if not self.verify_hash_chain(session_id):
            raise ValueError(f"Cadeia de eventos adulterada na sessão {session_id}!")

        if game_type == "chess":
            engine = EpistemicChessEngine()
            claims_reconstructed = []
            for evt in events:
                p = evt["payload"]
                if evt["event_type"] == "CHESS_MOVE":
                    uci = p.get("uci")
                    if uci:
                        engine.validate_and_apply_move(uci)
                elif evt["event_type"] == "CLAIM_CREATED":
                    claims_reconstructed.append(p)
                elif evt["event_type"] == "JUDGMENT_ISSUED":
                    cid = p.get("claim_id")
                    for c in claims_reconstructed:
                        if c.get("id") == cid:
                            c["status"] = p.get("verdict")
            return {
                "session_id": session_id,
                "events_count": len(events),
                "board": engine.to_dict(),
                "claims": claims_reconstructed
            }
        else:
            go_engine = GoEngine9x9()
            claims_reconstructed = []
            for evt in events:
                p = evt["payload"]
                if evt["event_type"] == "GO_MOVE":
                    coord = p.get("coord")
                    if coord:
                        go_engine.play_move(coord)
                elif evt["event_type"] == "CLAIM_CREATED":
                    claims_reconstructed.append(p)
                elif evt["event_type"] == "JUDGMENT_ISSUED":
                    cid = p.get("claim_id")
                    for c in claims_reconstructed:
                        if c.get("id") == cid:
                            c["status"] = p.get("verdict")
            return {
                "session_id": session_id,
                "events_count": len(events),
                "board": go_engine.to_dict(),
                "claims": claims_reconstructed
            }
