from uuid import uuid4

import pytest
from types import SimpleNamespace
from test_api import base_url, post

from app.main import app
from app.web_research.api import _run_lock, get_web_runner
from app.web_research.pipeline import Plan, ToolFailure, execute
from app.web_research.selection import Document
from test_web_pipeline import candidates


@pytest.fixture
def client(monkeypatch, base_url):
    monkeypatch.setenv('INFOEXPLORER_WEB_ENABLED', 'true')
    class Client:
        def post(self, path, json):
            status, data = post(base_url, __import__('json').dumps(json).encode(), path)
            return SimpleNamespace(status_code=status, json=lambda: data)
    yield Client()
    app.dependency_overrides.pop(get_web_runner, None)


def body(**changes):
    return {'runId': str(uuid4()), 'question': 'backend', 'language': 'en', **changes}


class OfflineRunner:
    def __init__(self):
        self.calls = 0

    def run(self, request):
        self.calls += 1
        return execute(Plan({'Q1': request.question}, (request.question,)),
            lambda *_: candidates('one'),
            lambda c, _: Document(c.source_id, c.host, c.title, ('backend documentation',)),
            run_id=request.run_id)


def install(runner):
    app.dependency_overrides[get_web_runner] = lambda: runner


def test_disabled_endpoint_has_no_tool_call(client, monkeypatch):
    monkeypatch.delenv('INFOEXPLORER_WEB_ENABLED')
    runner = OfflineRunner()
    install(runner)
    response = client.post('/internal/v2/research/run', json=body())
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'WEB_DISABLED'
    assert runner.calls == 0


def test_web_contract_identity_and_no_model_claim(client):
    runner = OfflineRunner()
    install(runner)
    request = body()
    response = client.post('/internal/v2/research/run', json=request)
    assert response.status_code == 200
    data = response.json()
    assert data['schemaVersion'] == 'web-research-v2'
    assert data['mode'] == 'web-extract'
    outcome = data['outcome']
    assert outcome['runId'] == request['runId']
    assert outcome['status'] == 'SUCCEEDED'
    assert outcome['coverage'] == 'unknown'
    assert outcome['usage']['modelCalls'] == 0
    assert outcome['reviewSnapshot'] is None
    assert len(outcome['evidence'][0]['evidenceKey']) == 64
    assert outcome['evidence'][0]['sourceId'] == outcome['sources'][0]['candidate']['sourceId']


@pytest.mark.parametrize('changes', [
    {'runId': 'invalid'}, {'run_id': str(uuid4())}, {'question': ' '},
    {'question': '😀' * 2001}, {'question': 123}, {'language': 'fr'},
    {'baseUrl': 'http://127.0.0.1'}, {'modelEnabled': True},
])
def test_invalid_input_and_tool_override_rejected_without_dispatch(client, changes):
    runner = OfflineRunner()
    install(runner)
    response = client.post('/internal/v2/research/run', json=body(**changes))
    assert response.status_code == 400
    assert runner.calls == 0


def test_busy_rejects_without_dispatch_and_does_not_release_other_run_lock(client):
    runner = OfflineRunner()
    install(runner)
    assert _run_lock.acquire(blocking=False)
    try:
        response = client.post('/internal/v2/research/run', json=body())
        assert response.status_code == 429
        assert runner.calls == 0
        assert _run_lock.locked()
    finally:
        _run_lock.release()


def test_runner_exception_releases_gate(client):
    class Broken:
        def run(self, _):
            raise RuntimeError('offline failure')
    from app.web_research.api import WebRequest, research_web
    with pytest.raises(RuntimeError):
        research_web(WebRequest.model_validate(body()), Broken())
    assert not _run_lock.locked()


def test_failed_execution_keeps_earlier_evidence_in_http_response(client):
    from app.web_research.budget import ExecutionBudget, Limits
    class InterruptedRunner:
        def run(self, request):
            now = [0.0]
            budget = ExecutionBudget(Limits(total_seconds=10, model_calls=0), lambda: now[0])
            def read(candidate, _):
                if candidate.requested_url.endswith('two'):
                    now[0] = 11.0
                return Document(candidate.source_id, candidate.host, candidate.title, ('backend documentation',))
            return execute(Plan({'Q1': request.question}, (request.question,)),
                lambda *_: candidates('one', 'two'), read, budget=budget, run_id=request.run_id)
    install(InterruptedRunner())
    response = client.post('/internal/v2/research/run', json=body())
    assert response.status_code == 200  # Completed transport, failed research outcome.
    outcome = response.json()['outcome']
    assert outcome['status'] == 'FAILED'
    assert outcome['completionReason'] == 'EXECUTION_DEADLINE'
    assert outcome['answer'] is None
    assert len(outcome['evidence']) == 1
    assert outcome['sources'][0]['status'] == 'READ'
    assert outcome['sources'][1]['status'] == 'FAILED'
    assert outcome['usage']['modelCalls'] == 0
