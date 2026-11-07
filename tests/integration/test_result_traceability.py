import pytest
import chess
from services.api.match.chess_player import ChessPlayer

from services.api.agents.gemini_adapter import ProviderUnavailableError
from services.api.models.schemas import CreateSessionRequest
from services.api.routes.reports import get_session_report
from services.api.storage.session_manager import SessionManager


def session(mode="audit", game="go"):
    manager = SessionManager()
    sid = manager.create_session(CreateSessionRequest(
        title="Verificar isolamento de credenciais", mode=mode, game=game,
        force_demo=True, depth="quick",
    ))["id"]
    manager.match_orchestrator.get_match_state(sid)["plies_budget"] = 2
    return manager, sid


@pytest.mark.parametrize("mode", ["audit", "debate"])
@pytest.mark.parametrize("game", ["chess", "go"])
def test_complete_result_and_export_without_provider(mode, game, monkeypatch):
    manager, sid = session(mode, game)
    def unavailable(**kwargs):
        raise ProviderUnavailableError("unavailable", status_code=503)
    monkeypatch.setattr(manager.gemini_adapter, "generate_match_synthesis", unavailable)
    state = manager.match_orchestrator.run_full_match(sid)
    result = state["conclusion"]
    assert state["is_complete"] and result["final_synthesis"]
    assert result["synthesis_source"] == "deterministic_fallback"
    assert result["epistemic_result"] == "OPEN_HYPOTHESIS"
    assert result["next_steps"] and result["evidence_trace"]
    events = manager.event_store.get_events(sid)
    sealed = next(e for e in events if e["event_type"].startswith("RESEARCH_MATCH_"))
    assert sealed["payload"]["conclusion"] == result
    seqs = {e["seq"] for e in events}
    for row in result["evidence_trace"]:
        assert set(row["event_seqs"]) <= seqs
        if mode == "audit" and row["finding"]:
            assert row["finding"]["compliance_status"] == "INCONCLUSIVE"
    data = get_session_report(sid, "json", manager)
    assert data["chain_verified_at_export"]
    assert data["research_match"]["timeline"]
    md = get_session_report(sid, "markdown", manager).body.decode()
    assert "Rastreabilidade" in md and "Próximos passos" in md
    assert result["final_synthesis"] in md
    assert str(result["evidence_trace"][0]["piece_id"]) in md


def test_interrupted_research_has_partial_result_and_can_retry(monkeypatch):
    manager, sid = session()
    orch = manager.match_orchestrator
    orch.run_next_stage(sid)
    original = orch._stage_2_research_side
    def unavailable(*args, **kwargs):
        raise ProviderUnavailableError("unavailable", status_code=503)
    monkeypatch.setattr(orch, "_stage_2_research_side", unavailable)
    with pytest.raises(ProviderUnavailableError):
        orch.run_next_stage(sid)
    state = orch.get_match_state(sid)
    assert not state["is_complete"] and state["current_stage"] == 1
    assert state["conclusion"]["termination_criterion"] == "INTERRUPTED"
    assert state["conclusion"]["is_provisional"]
    assert get_session_report(sid, "json", manager)["research_match"]["conclusion"]
    monkeypatch.setattr(orch, "_stage_2_research_side", original)
    assert orch.run_full_match(sid)["is_complete"]


def test_capture_and_quote_do_not_prove_compliance():
    manager, sid = session()
    orch = manager.match_orchestrator
    piece = {"piece_id": "test", "claim": "MFA implementado", "supporting_artifacts": [
        {"verified": True, "quote_text": "MFA é recomendado"}
    ]}
    sess = manager.sessions[sid]
    a = orch._build_control_audit(sess, 1, "black", piece, None, "MFA é recomendado", False)
    b = orch._build_control_audit(sess, 9, "white", piece, None, "MFA é recomendado", True)
    assert a == b and a["compliance_status"] == "INCONCLUSIVE"


def test_html_escapes_untrusted_content_and_export_verifies_chain():
    manager, sid = session()
    manager.sessions[sid]["title"] = '<script>alert("unsafe")</script>'
    response = get_session_report(sid, "html", manager).body.decode()
    assert "<script>" not in response and "&lt;script&gt;" in response
    manager.event_store._events[sid][0]["payload"]["tampered"] = True
    assert not get_session_report(sid, "json", manager)["chain_verified_at_export"]


def test_completed_result_is_idempotent_and_sealed():
    manager, sid = session()
    orch = manager.match_orchestrator
    result = orch.run_full_match(sid)
    events = len(manager.event_store.get_events(sid))
    assert orch.run_full_match(sid) == result
    assert len(manager.event_store.get_events(sid)) == events
    assert manager.event_store.verify_hash_chain(sid)


def test_bounded_chess_search_preserves_board_and_determinism():
    board = chess.Board("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
    before = board.fen()
    player = ChessPlayer("bounded", max_nodes_per_candidate=16)
    first = player.rank_moves(board)
    assert board.fen() == before and not board.move_stack
    assert {m for _, m in first} == set(board.legal_moves)
    assert player._nodes <= 17
    assert first == ChessPlayer("bounded", max_nodes_per_candidate=16).rank_moves(board)
