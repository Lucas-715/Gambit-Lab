import copy
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from services.api.main import app
from services.api.match.decision import comparison_plan, decide
from services.api.models.schemas import CreateSessionRequest
from services.api.storage.session_manager import SessionManager
from services.api.routes.reports import get_session_report

TOPIC = 'No Brasil governos de esquerda são melhores que os de direita de acordo com a história?'


def prepared(game='go'):
    manager = SessionManager()
    sid = manager.create_session(CreateSessionRequest(title=TOPIC, mode='debate', game=game, force_demo=True))["id"]
    state = manager.match_orchestrator.get_match_state(sid)
    state['plies_budget'] = 2
    return manager, sid


@pytest.mark.parametrize('game', ['chess', 'go'])
def test_one_request_delivers_terminal_match_and_decision(game):
    manager, sid = prepared(game)
    from services.api.routes.match import get_manager
    app.dependency_overrides[get_manager] = lambda: manager
    try:
        response = TestClient(app).post(f'/api/v1/sessions/{sid}/match')
    finally:
        app.dependency_overrides.pop(get_manager, None)
    assert response.status_code == 200
    state = response.json()
    assert state['is_complete'] and state['status'] == 'COMPLETED' and not state['resumable']
    assert state['conclusion']['ludic_result'] in ['DRAW', 'WHITE_WINS', 'BLACK_WINS']
    assert state['conclusion']['termination_criterion'] == 'ADJUDICATED'
    assert state['conclusion']['decision']['total_criteria'] == 6
    assert state['conclusion']['decision']['code'] == 'DEMONSTRATION'
    assert not state['conclusion']['is_provisional']
    assert manager.event_store.verify_hash_chain(sid)


def test_history_is_not_electoral_campaign():
    manager, sid = prepared('chess')
    orch = manager.match_orchestrator
    state = orch.run_full_match(sid)
    assert orch._detect_topic_domain(TOPIC) == 'historical_comparison'
    dimension = orch._get_domain_role_dimension('historical_comparison', 'queen', 'd1', 'pro', TOPIC)
    assert 'candidatura' not in dimension and 'comparar governos' in dimension
    events = manager.event_store.get_events(sid)
    rules = next(e for e in events if e['event_type'] == 'MATCH_RULES_DECLARED')
    assert rules['payload']['comparison_plan'] == state['comparison_plan']


def fixture_review():
    quote = 'Indicadores comparados nos períodos A e B, com a mesma metodologia.'
    trace = [{'piece_id': 'p1', 'evidence': [{'artifact_id': 'a1', 'quote_text': quote, 'verified': True}]}]
    review = {'criterion_id': 'C1', 'verdict': 'PRO', 'reason': 'A comparação favorece a tese neste indicador.',
              'comparison_scope': 'Períodos A e B, mesma metodologia.',
              'citations': [{'piece_id': 'p1', 'artifact_id': 'a1', 'quote_text': quote}]}
    return trace, review


def test_jury_validates_citations_counts_once_and_preserves_missing_criteria():
    trace, review = fixture_review()
    plan = comparison_plan(TOPIC, 'debate')
    result = decide(plan, [review, review], trace, 'LIVE_DOCUMENTS', 'debate')
    assert result['code'] == 'PRO_BY_CRITERIA'
    assert result['pro_points'] == 1 and result['assessed_criteria'] == 1
    assert result['total_criteria'] == 6
    assert result['criteria'][1]['verdict'] == 'NOT_ESTABLISHED'
    review['citations'][0]['quote_text'] = 'Fabricated quote'
    assert decide(plan, [review], trace, 'LIVE_DOCUMENTS', 'debate')['code'] == 'NOT_DEMONSTRATED'


@pytest.mark.parametrize('bad', [None, 'not a list', [{'criterion_id': []}], [{'criterion_id': 'C1', 'citations': [{'piece_id': []}]}]])
def test_invalid_model_reviews_cannot_break_final_result(bad):
    result = decide(comparison_plan(TOPIC, 'debate'), bad, [], 'LIVE_DOCUMENTS', 'debate')
    assert result['code'] == 'NOT_DEMONSTRATED'


def test_legacy_budget_session_closes_without_more_plies():
    manager, sid = prepared()
    orch = manager.match_orchestrator
    state = orch.run_full_match(sid)
    state.update(status='BUDGET_EXHAUSTED', resumable=True)
    manager.sessions[sid]['_match_internal']['play']['finished'] = False
    moves = copy.deepcopy(state['timeline'])
    orch.resume_match(sid, extra_plies=12)
    assert state['timeline'] == moves and state['status'] == 'COMPLETED'
    assert not state['resumable'] and manager.event_store.verify_hash_chain(sid)


def test_duplicate_full_requests_are_serialized_and_idempotent():
    manager, sid = prepared()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: manager.match_orchestrator.run_full_match(sid), range(2)))
    assert results[0] == results[1]
    events = manager.event_store.get_events(sid)
    assert sum(e['event_type'] == 'MATCH_ADJUDICATED' for e in events) == 1
    assert manager.event_store.verify_hash_chain(sid)


def test_model_review_drives_exported_decision(monkeypatch):
    manager, sid = prepared()
    orch = manager.match_orchestrator
    for _ in range(5):
        orch.run_next_stage(sid)
    sess = manager.sessions[sid]
    # Inject an already verified fixture at the jury boundary; no real provider call.
    sess['execution_mode'] = 'LIVE_DOCUMENTS'
    piece = sess['research_match']['pieces'][0]
    quote = 'Indicadores comparáveis em dois períodos.'
    piece['supporting_artifacts'] = [{'artifact_id': 'a', 'quote_text': quote, 'verified': True, 'title': 'Série histórica', 'sha256': 'test'}]
    def synthesis(**kwargs):
        return {'final_synthesis': 'Comparação limitada ao indicador documentado.', 'key_arguments_pro': [], 'key_arguments_contra': [], 'limitations': [],
                'criterion_reviews': [{'criterion_id': 'C1', 'verdict': 'CONTRA', 'reason': 'O indicador contraria a tese no período analisado.', 'comparison_scope': 'Dois períodos equivalentes.',
                    'citations': [{'piece_id': piece['piece_id'], 'artifact_id': 'a', 'quote_text': quote}]}]}
    monkeypatch.setattr(manager.gemini_adapter, 'generate_match_synthesis', synthesis)
    state = orch.run_full_match(sid)
    assert state['conclusion']['decision']['code'] == 'CONTRA_BY_CRITERIA'
    md = get_session_report(sid, 'markdown', manager).body.decode()
    assert 'Decisão por critérios' in md and 'Dois períodos equivalentes.' in md
