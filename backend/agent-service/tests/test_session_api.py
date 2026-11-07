from types import SimpleNamespace
from test_api import base_url, post
import json
import pytest
from app.main import app
from app.web_research.api import _run_lock
from app.web_research.session_api import get_session_runner
from session_fixtures import FixtureRunner

REQUEST = {'runId':'11111111-1111-4111-8111-111111111111','question':'public topic','language':'en'}

@pytest.fixture
def client(monkeypatch, base_url):
    monkeypatch.setenv('INFOEXPLORER_WEB_MODEL_ENABLED','true')
    app.dependency_overrides[get_session_runner] = FixtureRunner
    class Client:
        def post(self,path,json):
            status,data=post(base_url,__import__('json').dumps(json).encode(),path)
            return SimpleNamespace(status_code=status,json=lambda:data)
    yield Client()
    app.dependency_overrides.pop(get_session_runner, None)

@pytest.mark.parametrize('question,reason', [('public topic','EVIDENCE_SUFFICIENT'),
    ('supplement','SUPPLEMENT_ROUND_LIMIT'),('fail report','MODEL_INVALID_RESPONSE'),
    ('fallback','EVIDENCE_SUFFICIENT'),('auth failure','MODEL_AUTH_ERROR'),('empty','NO_USABLE_EVIDENCE')])
def test_session_http_contract(client, question, reason):
    response=client.post('/internal/v3/research/run',json={**REQUEST,'question':question})
    assert response.status_code==200
    body=response.json()
    assert body['schemaVersion']=='web-research-v3'
    assert body['session']['runId']==REQUEST['runId']
    assert body['session']['stopReason']==reason
    if question=='fail report':
        assert body['session']['outcome']['evidence']
        assert body['session']['report'] is None

def test_opt_in_and_shared_gate(client,monkeypatch):
    monkeypatch.setenv('INFOEXPLORER_WEB_MODEL_ENABLED','false')
    assert client.post('/internal/v3/research/run',json=REQUEST).status_code==503
    monkeypatch.setenv('INFOEXPLORER_WEB_MODEL_ENABLED','true')
    _run_lock.acquire()
    try:
        assert client.post('/internal/v3/research/run',json=REQUEST).status_code==429
    finally:
        _run_lock.release()

def test_rejects_client_tools_budget_and_invalid_identity(client):
    for extra in ({'tools':['shell']},{'budget':1000},{'runId':'bad'}):
        assert client.post('/internal/v3/research/run',json={**REQUEST,**extra}).status_code==400

def test_web_model_opt_in_does_not_enable_legacy_wiki(monkeypatch):
    from app.model import get_report_generator, ModelSettings
    from app.web_research.model_completion import JsonCompletion
    monkeypatch.setenv('INFOEXPLORER_WEB_MODEL_ENABLED','true')
    monkeypatch.setenv('INFOEXPLORER_MODEL_ENABLED','false')
    monkeypatch.setenv('MODEL_BASE_URL','https://models.example.org/v1')
    monkeypatch.setenv('MODEL_ALLOWED_HOST','models.example.org')
    monkeypatch.setenv('MODEL_NAME','synthetic')
    monkeypatch.setenv('MODEL_API_KEY','synthetic-not-a-secret')
    assert JsonCompletion.from_env().settings.model=='synthetic'
    assert ModelSettings.from_env() is None
    assert get_report_generator().settings is None
