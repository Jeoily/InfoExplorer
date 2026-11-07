from dataclasses import asdict, replace
import json
import socket

import pytest

from app.web_research import recording as r
from app.web_research.pipeline import ToolFailure
from test_research_session import Model, search, read


def normalized(outcome):
    data = dict(outcome)
    data["usage"] = {k:v for k,v in data["usage"].items() if k != "remaining_seconds"}
    return data


def capture(tmp_path, model=None, **kwargs):
    result = r.record_run(tmp_path, 'fixture', 'Public topic', 'en',
                          kwargs.pop('search', search), kwargs.pop('read', read), model or Model(), **kwargs)
    path = next(tmp_path.iterdir())
    return path, result


def test_private_retrieval_terms_survive_replay_without_public_contract_change(tmp_path):
    def bilingual(stage, output):
        if stage=='plan':
            output['questions'][0]['retrievalTerms']=['公开主题','public topic']
    path, original=capture(tmp_path, Model(mutate=bilingual))
    assert 'retrievalTerms' not in original.plan['questions'][0]
    _, events=r.load_record(path)
    saved=next(e['data']['output'] for e in events if e['event']=='model_end' and e['data'].get('stage')=='plan')
    assert saved['questions'][0]['retrievalTerms']==['公开主题','public topic']
    assert r.replay(path)['session']['report']==original.report


@pytest.mark.parametrize('supplement', [False, True])
def test_full_replay_without_network(tmp_path, monkeypatch, supplement):
    path, original = capture(tmp_path, Model(supplement=supplement))
    def forbidden(*args, **kwargs):
        raise AssertionError('NETWORK_FORBIDDEN')
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    replayed = r.replay(path)
    assert replayed['externalRequests'] == 0
    assert replayed['session']['report'] == original.report
    assert normalized(replayed['session']['outcome']) == normalized(asdict(original.outcome))
    assert replayed['session']['plan'] == original.plan
    assert r.check_report(path)['answer'] == original.outcome.answer
    assert r.inspect_record(path)['recordStatus'] == 'COMPLETE'
    assert r.reselect(path)['added'] == []
    assert r.reselect(path)['removed'] == []


def test_failed_report_only_records_safe_error(tmp_path):
    model = Model()
    def invalid(stage, request, timeout):
        return b'PRIVATE_BAD_RAW_SENTINEL' if stage == 'report' else model(stage, request, timeout)
    path, original = capture(tmp_path, invalid)
    assert original.outcome.status == 'FAILED'
    assert 'PRIVATE_BAD_RAW_SENTINEL' not in ''.join(p.read_text(encoding='utf-8') for p in path.glob('*.json'))
    assert r.replay(path)['session']['outcome']['completion_reason'] == 'MODEL_INVALID_RESPONSE'
    assert any(s.get('code') == 'MODEL_INVALID_RESPONSE' for s in r.inspect_record(path)['stages'])
    assert r.report_input(path)['data']['evidence']
    with pytest.raises(r.ReplayError, match='NO_VALIDATED_REPORT'):
        r.check_report(path)


def test_tool_failure_replay(tmp_path):
    def fail(*_):
        raise ToolFailure('SEARCH_UNAVAILABLE')
    path, result = capture(tmp_path, search=fail)
    assert normalized(r.replay(path)['session']['outcome']) == normalized(asdict(result.outcome))


def test_changed_prompt_fails_closed(tmp_path, monkeypatch):
    path, _ = capture(tmp_path)
    from app.web_research import research_session as session
    monkeypatch.setattr(session, 'SAFETY', session.SAFETY + ' changed')
    with pytest.raises(r.ReplayError, match='REPLAY_INPUT_OR_SEQUENCE_MISMATCH'):
        r.replay(path)


@pytest.mark.parametrize('change,code', [('hash','RECORD_HASH'),('path','INVALID_EVENT_PATH'),('incomplete','TRACE_INCOMPLETE')])
def test_damaged_records_rejected(tmp_path, change, code):
    path, _ = capture(tmp_path)
    manifest = json.loads((path/'manifest.json').read_text())
    if change == 'hash':
        (path/'000.json').write_bytes(b'{}')
    elif change == 'path':
        manifest['events'][0]['file'] = '../outside.json'
    else:
        manifest['status'] = 'RECORDING'
    (path/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(r.ReplayError, match=code):
        r.replay(path)


def test_record_limit_does_not_fail_research(tmp_path, monkeypatch):
    monkeypatch.setattr(r, 'MAX_EVENTS', 2)
    path, result = capture(tmp_path)
    assert result.outcome.status == 'SUCCEEDED'
    assert r.inspect_record(path)['recordStatus'] == 'INCOMPLETE'
    with pytest.raises(r.ReplayError, match='TRACE_INCOMPLETE'):
        r.replay(path)


def test_full_documents_available_for_reselection(tmp_path, monkeypatch):
    extra = 'A previously unselected public paragraph about an unrelated subject.'
    def full_read(candidate, timeout):
        return replace(read(candidate, timeout), paragraphs=('Public topic evidence.', extra))
    path, _ = capture(tmp_path, read=full_read)
    seen = []
    original = r.select_passages
    def select(documents, questions, **kwargs):
        seen.extend(documents)
        return original(documents, questions, **kwargs)
    monkeypatch.setattr(r, 'select_passages', select)
    r.reselect(path)
    assert extra in seen[0].paragraphs


def test_fixed_evidence_generation_uses_one_completion(tmp_path):
    path, original = capture(tmp_path)
    before = {p.name:p.read_bytes() for p in path.iterdir()}
    model = Model()
    result = r.regenerate_report(path, model)
    assert len(model.calls) == 1
    assert model.calls[0][0] == 'report'
    assert model.calls[0][1]['data'] == r.report_input(path)['data']
    assert result['answer'] == original.outcome.answer
    assert {p.name:p.read_bytes() for p in path.iterdir()} == before


def test_regeneration_still_enforces_quotes(tmp_path):
    path, _ = capture(tmp_path)
    def mutate(stage, data):
        data['claims'][0]['supportingQuotes'][0]['quote'] = 'This quote does not occur in the evidence'
    with pytest.raises(ValueError):
        r.regenerate_report(path, Model(mutate=mutate))


def test_disk_failure_after_initial_manifest_preserves_business_result(tmp_path, monkeypatch):
    original = r.write_file
    calls = 0
    def write(path, raw):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise OSError('FAKE_DISK_FAILURE')
        original(path, raw)
    monkeypatch.setattr(r, 'write_file', write)
    path, result = capture(tmp_path)
    assert result.outcome.status == 'SUCCEEDED'
    assert r.inspect_record(path)['recordStatus'] == 'RECORDING'
    with pytest.raises(r.ReplayError, match='TRACE_INCOMPLETE'):
        r.replay(path)


def test_unfinished_stage_is_visible(tmp_path):
    from uuid import uuid4
    recorder = r.Recorder(tmp_path, 'Public topic', 'en', str(uuid4()), 'fixture')
    recorder('tool_start', {'kind':'search', 'input':'public topic'})
    summary = r.inspect_record(recorder.path)
    assert summary['stages'] == [{'stage':'search', 'status':'INCOMPLETE'}]


def test_failed_plan_fallback_can_replay(tmp_path):
    def mutate(stage, data):
        if stage == 'plan':
            data['unexpected'] = True
    path, result = capture(tmp_path, Model(mutate=mutate))
    assert r.replay(path)['session']['report'] == result.report
    assert r.inspect_record(path)['stages'][0]['status'] == 'FAILED'


def test_reselection_detects_changed_choice(tmp_path, monkeypatch):
    path, _ = capture(tmp_path)
    monkeypatch.setattr(r, 'select_passages', lambda *_, **__: ())
    diff = r.reselect(path)
    assert diff['removed'] and not diff['added']
