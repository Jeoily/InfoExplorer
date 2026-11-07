import json

import pytest

from app.model import ModelError, ModelSettings, _slot, bounded_request
from app.web_research.model_completion import JsonCompletion
from app.web_research.pipeline import ToolFailure
from app.web_research.research_session import run_session


def settings():
    return ModelSettings('https://models.example.org/v1', 'fixture', 'offline-placeholder')


def request():
    return {'instructions': 'JSON only', 'data': {'question': 'public topic'}}


def envelope(content='{}', finish='stop', **extra):
    return json.dumps({'choices': [{'finish_reason': finish,
        'message': {'content': content, **extra}}]}).encode()


def test_adapter_uses_json_text_no_tools_and_propagates_remaining_timeout():
    def transport(config, body, *, timeout):
        payload = json.loads(body)
        assert config.model == 'fixture'
        assert timeout == .5
        assert 'tools' not in payload
        assert not payload['stream']
        assert payload['messages'][0]['role'] == 'system'
        assert json.loads(payload['messages'][1]['content']) == request()['data']
        return envelope('{"scope":"public"}')
    assert JsonCompletion(settings(), transport)('plan', request(), .5) == b'{"scope":"public"}'


@pytest.mark.parametrize('raw', [envelope(finish='length'), envelope(tool_calls=[{'name':'shell'}]),
                                envelope(content=None), b'not json', b' ' * 65537],
                         ids=['truncated','tool-call','no-content','malformed','oversized'])
def test_adapter_rejects_invalid_provider_response_and_releases_slot(raw):
    adapter = JsonCompletion(settings(), lambda *a, **kw: raw)
    with pytest.raises(ToolFailure, match='MODEL_INVALID_RESPONSE'):
        adapter('plan', request(), 1)
    assert _slot.acquire(blocking=False)
    _slot.release()


def test_auth_failure_stops_before_search_and_has_no_secret_in_trace():
    def transport(*args, **kwargs):
        raise ModelError('MODEL_AUTH_ERROR')
    def forbidden(*args):
        pytest.fail('Must not search after authentication failure')
    result = run_session('public topic', 'en', forbidden, forbidden, JsonCompletion(settings(), transport))
    assert result.stop_reason == 'MODEL_AUTH_ERROR'
    assert result.usage.model_calls == 1
    assert result.usage.searches == 0
    assert 'offline-placeholder' not in repr(result)


def test_busy_does_not_invoke_transport():
    assert _slot.acquire(blocking=False)
    try:
        with pytest.raises(ToolFailure, match='MODEL_BUSY'):
            JsonCompletion(settings(), lambda *a, **kw: pytest.fail('No call'))('plan', request(), 1)
    finally:
        _slot.release()


@pytest.mark.parametrize('timeout', [0, -1, 46, float('nan'), True])
def test_transport_rejects_invalid_deadline_before_process_start(timeout):
    with pytest.raises(ModelError, match='MODEL_CONFIG_ERROR'):
        bounded_request(settings(), b'{}', timeout=timeout)
