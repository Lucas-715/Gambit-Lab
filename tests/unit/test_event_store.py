"""
Unit tests for EventStore, SHA-256 Hash Chaining, Replay, and Concurrency
(RNF-02, RF-42, RN-30, RN-31, RN-32, AC-14, AC-18)
"""
import pytest
from services.api.storage.event_store import EventStore, ConcurrencyConflictError, compute_event_hash


def test_event_store_append_and_hash_chain():
    store = EventStore()
    sess_id = "test_sess_01"

    # Append first event (genesis SESSION_CREATED with expected_version = 1)
    evt1 = store.append_event(
        session_id=sess_id,
        expected_version=1,
        event_type="SESSION_CREATED",
        payload={"title": "Test Session"}
    )
    assert evt1["seq"] == 1
    assert evt1["prev_hash"] == "GENESIS_HASH_GAMBIT_LAB_V2"
    assert len(evt1["event_hash"]) == 64

    # Append second event (move 1, expected_version = 1)
    evt2 = store.append_event(
        session_id=sess_id,
        expected_version=1,
        event_type="CHESS_MOVE",
        payload={"uci": "e2e4", "san": "e4"}
    )
    assert evt2["seq"] == 2
    assert evt2["prev_hash"] == evt1["event_hash"]

    # Append third event (move 2, expected_version = 2)
    evt3 = store.append_event(
        session_id=sess_id,
        expected_version=2,
        event_type="CHESS_MOVE",
        payload={"uci": "e7e5", "san": "e5"}
    )
    assert evt3["seq"] == 3
    assert evt3["prev_hash"] == evt2["event_hash"]

    # Verify whole chain integrity
    assert store.verify_hash_chain(sess_id)


def test_concurrency_conflict_expected_version():
    """RNF-17: Controle otimista de versão (HTTP 409)."""
    store = EventStore()
    sess_id = "test_sess_02"

    store.append_event(sess_id, expected_version=1, event_type="INIT", payload={"msg": "start"})

    # Client tries to send an action with stale expected_version=99 instead of 1
    with pytest.raises(ConcurrencyConflictError):
        store.append_event(sess_id, expected_version=99, event_type="MOVE", payload={"uci": "e2e4"})


def test_replay_session_chess_deterministic():
    """AC-18: Replay reconstrói exatamente o mesmo estado a partir dos eventos."""
    store = EventStore()
    sess_id = "replay_chess"

    store.append_event(sess_id, expected_version=1, event_type="SESSION_CREATED", payload={"title": "Replay"})
    store.append_event(sess_id, expected_version=1, event_type="CHESS_MOVE", payload={"uci": "e2e4"})
    store.append_event(sess_id, expected_version=2, event_type="CHESS_MOVE", payload={"uci": "e7e5"})
    store.append_event(sess_id, expected_version=3, event_type="CHESS_MOVE", payload={"uci": "g1f3"})

    replayed = store.replay_session(sess_id, game_type="chess")
    assert replayed["events_count"] == 4
    board = replayed["board"]
    assert board["turn"] == "black"
    assert "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R" in board["fen"]


def test_replay_session_go_deterministic():
    """AC-18: Replay Go a partir de eventos."""
    store = EventStore()
    sess_id = "replay_go"

    store.append_event(sess_id, expected_version=1, event_type="SESSION_CREATED", payload={"title": "Go Replay"})
    store.append_event(sess_id, expected_version=1, event_type="GO_MOVE", payload={"coord": "D4"})
    store.append_event(sess_id, expected_version=2, event_type="GO_MOVE", payload={"coord": "E5"})

    replayed = store.replay_session(sess_id, game_type="go")
    assert replayed["events_count"] == 3
    board = replayed["board"]
    assert len(board["stones"]) == 2
    coords = [s["coord"] for s in board["stones"]]
    assert "D4" in coords
    assert "E5" in coords
