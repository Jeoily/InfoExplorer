import json
import multiprocessing
import time

import pytest

import app.model as module
from app.model import ModelError, ModelSettings, ReportGenerator, parse_answer
from app.search import WikipediaSearch


def report():
    return WikipediaSearch().parse({"query": {"pages": [
        {"title": "Example", "extract": "Public example evidence."}]}}, "example")


def response(claims=None):
    return json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
        "claims": claims if claims is not None else [{"text": "Example claim", "evidenceIds": ["E1"]}],
        "limitations": ["Only supplied excerpts were considered."]})}}]}).encode()


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    for name in ("MODEL_BASE_URL", "MODEL_NAME", "MODEL_ALLOWED_HOST", "MODEL_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("INFOEXPLORER_MODEL_ENABLED", "false")


def settings():
    return ModelSettings("https://models.example.org/v1", "fixture-model", "test-only-placeholder")


def test_disabled_does_not_require_or_use_credentials():
    assert ModelSettings.from_env() is None
    original = report()
    assert ReportGenerator(None, lambda *_: pytest.fail("Unexpected call")).generate(original) is original


@pytest.mark.parametrize("field,value", [
    ("MODEL_BASE_URL", "http://models.example.org/v1"),
    ("MODEL_BASE_URL", "https://other.example.org/v1"),
    ("MODEL_BASE_URL", "https://user@models.example.org/v1"),
    ("MODEL_BASE_URL", "https://@models.example.org/v1"),
    ("MODEL_BASE_URL", "https://models.example.org/v1?secret=x"),
    ("MODEL_BASE_URL", "https://models.example.org:8443/v1"),
    ("MODEL_NAME", ""), ("MODEL_API_KEY", "line\nbreak"),
    ("INFOEXPLORER_MODEL_ENABLED", "yes"),
])
def test_configuration_fails_closed(monkeypatch, field, value):
    for name, content in {"INFOEXPLORER_MODEL_ENABLED": "true", "MODEL_BASE_URL": settings().base_url,
                          "MODEL_NAME": "fixture-model", "MODEL_ALLOWED_HOST": "models.example.org",
                          "MODEL_API_KEY": "test-only-placeholder"}.items():
        monkeypatch.setenv(name, content)
    monkeypatch.setenv(field, value)
    with pytest.raises(ModelError, match="MODEL_CONFIG_ERROR"):
        ModelSettings.from_env()


def test_success_preserves_evidence_and_never_sends_key_or_urls_in_prompt():
    calls = []
    def transport(config, body):
        calls.append(body)
        data = json.loads(body)
        assert data["max_tokens"] == 1200
        assert "tools" not in data
        assert config.api_key not in body.decode()
        assert report().sources[0] not in body.decode()
        return response()
    original = report()
    generated = ReportGenerator(settings(), transport).generate(original)
    assert len(calls) == 1
    assert generated.evidence == original.evidence
    assert generated.sources == original.sources
    assert "[E1]" in generated.answer
    assert generated.generation.model == "fixture-model"
    assert generated.generation.promptVersion == module.PROMPT_VERSION
    assert len(generated.generation.inputHash) == 64
    assert original.generation is None
    assert settings().api_key not in repr(settings())


@pytest.mark.parametrize("claims", [
    [{"text": "false", "evidenceIds": ["E9"]}],
    [{"text": "no evidence", "evidenceIds": []}],
    [{"text": "<script>bad</script>", "evidenceIds": ["E1"]}],
    [{"text": "hidden [E9]", "evidenceIds": ["E1"]}],
    [{"text": "https://evil.example", "evidenceIds": ["E1"]}],
    [{"text": "a" * 601, "evidenceIds": ["E1"]}],
    [{"text": "x", "evidenceIds": ["E1", "E1"]}],
    [{"text": "bad\ud800", "evidenceIds": ["E1"]}],
])
def test_rejects_forged_citations_and_unsafe_output(claims):
    with pytest.raises(ModelError, match="MODEL_INVALID_RESPONSE"):
        parse_answer(response(claims), report())


@pytest.mark.parametrize("raw", [b"{", b"[]", b'{"choices":[]}',
    b'{"choices":[{"finish_reason":"length","message":{"content":"{}"}}]}',
    b'{"choices":[{"finish_reason":"stop","message":{"tool_calls":[{}],"content":"{}"}}]}'])
def test_malformed_truncated_or_tool_output_is_rejected(raw):
    with pytest.raises(ModelError, match="MODEL_INVALID_RESPONSE"):
        parse_answer(raw, report())


@pytest.mark.parametrize("payload,reason", [
    ({"choices": [{"finish_reason": "length"}]}, "finish_reason"),
    ({"choices": [{"finish_reason": "stop", "message": None}]}, "message_shape"),
    ({"choices": [{"finish_reason": "stop", "message": {"content": "private-marker"}}]}, "content_json"),
    ({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
        "claims": [{"text": "private-marker", "evidenceIds": ["E9"]}],
        "limitations": ["limited"]})}}]}, "evidence_ids"),
])
def test_diagnostics_classify_rejection_without_logging_provider_content(caplog, payload, reason):
    with pytest.raises(ModelError, match="MODEL_INVALID_RESPONSE"):
        parse_answer(json.dumps(payload).encode(), report())
    assert caplog.messages == [f"MODEL_RESPONSE_REJECTED reason={reason}"]
    assert "private-marker" not in caplog.text


def test_no_evidence_skips_model_and_insufficient_evidence_can_abstain():
    empty = WikipediaSearch().parse({"batchcomplete": True}, "example")
    assert ReportGenerator(settings(), lambda *_: pytest.fail("Unexpected call")).generate(empty) is empty
    assert "证据不足" in parse_answer(response([]), report())


@pytest.mark.parametrize("claims,limits,reason", [
    ({}, ["limited"], "claims_type"),
    ([{"text": "claim", "evidenceIds": ["E1"]}] * 9, ["limited"], "claims_count"),
    ([], "private-marker", "limitations_type"),
    ([], [], "limitations_count"),
    ([], ["private-marker"] * 5, "limitations_count"),
])
def test_report_limits_reject_without_silent_truncation(caplog, claims, limits, reason):
    raw = json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
        "claims": claims, "limitations": limits})}}]}).encode()
    with pytest.raises(ModelError, match="MODEL_INVALID_RESPONSE"):
        parse_answer(raw, report())
    assert caplog.messages == [f"MODEL_RESPONSE_REJECTED reason={reason}"]


@pytest.mark.parametrize("count,limit_count", [(0, 1), (8, 4)])
def test_report_count_boundaries_are_accepted(count, limit_count):
    raw = json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
        "claims": [{"text": "claim", "evidenceIds": ["E1"]}] * count,
        "limitations": ["limited"] * limit_count})}}]}).encode()
    assert "局限" in parse_answer(raw, report())


def test_failure_is_not_retried_and_slot_is_released():
    calls = []
    def fail(*args):
        calls.append(1)
        raise ModelError("MODEL_RATE_LIMITED")
    with pytest.raises(ModelError, match="MODEL_RATE_LIMITED"):
        ReportGenerator(settings(), fail).generate(report())
    assert calls == [1]
    assert ReportGenerator(settings(), lambda *_: response()).generate(report()).generation


def test_concurrency_rejects_without_queue_or_model_call():
    with module._slot:
        with pytest.raises(ModelError, match="MODEL_BUSY"):
            ReportGenerator(settings(), lambda *_: pytest.fail("Unexpected call")).generate(report())


def test_input_size_rejected_before_transport():
    oversized = report().model_copy(update={"query": "a" * 33000})
    with pytest.raises(ModelError, match="MODEL_INPUT_TOO_LARGE"):
        ReportGenerator(settings(), lambda *_: pytest.fail("Unexpected call")).generate(oversized)


@pytest.mark.parametrize("status,raw,code", [(302, b"", "MODEL_UNAVAILABLE"),
    (401, b"", "MODEL_AUTH_ERROR"), (429, b"", "MODEL_RATE_LIMITED"),
    (500, b"", "MODEL_UNAVAILABLE"), (200, b"a" * 65537, "MODEL_INVALID_RESPONSE")],
    ids=["redirect", "auth", "rate-limit", "server-error", "oversized"])
def test_transport_bounds_response_and_never_follows_redirect(monkeypatch, status, raw, code):
    calls = []
    class Connection:
        def __init__(self, *args, **kwargs): pass
        def request(self, *args, **kwargs): calls.append(1)
        def getresponse(self): return self
        def getheader(self, *args): return "application/json"
        def read(self, amount):
            assert amount == 65537
            return raw
        def close(self): pass
    Connection.status = status
    monkeypatch.setattr(module.http.client, "HTTPSConnection", Connection)
    with pytest.raises(ModelError, match=code):
        module._http_post(settings().base_url + "/chat/completions", "test-only", b"{}")
    assert calls == [1]


def sleeping_worker(pipe, *args):
    time.sleep(10)


def success_worker(pipe, *args):
    pipe.send((None, response()))
    pipe.close()


def test_http_socket_timeout_uses_call_budget(monkeypatch):
    captured = []
    class Connection:
        status = 200
        def __init__(self, *args, **kwargs): captured.append(kwargs['timeout'])
        def request(self, *args, **kwargs): pass
        def getresponse(self): return self
        def getheader(self, *args): return 'application/json'
        def read(self, amount): return b'{}'
        def close(self): pass
    monkeypatch.setattr(module.http.client, 'HTTPSConnection', Connection)
    module._http_post('https://models.example.org/v1/chat/completions', 'fake', b'{}', 17.5)
    assert captured == [17.5]


def test_deadline_terminates_real_child_process(monkeypatch):
    before = {child.pid for child in multiprocessing.active_children()}
    monkeypatch.setattr(module, "_worker", sleeping_worker)
    monkeypatch.setattr(module, "MODEL_DEADLINE", 0.2)
    start = time.monotonic()
    with pytest.raises(ModelError, match="MODEL_TIMEOUT"):
        module.bounded_request(settings(), b"{}")
    assert time.monotonic() - start < 4
    assert {child.pid for child in multiprocessing.active_children()} == before


def test_real_child_process_returns_response(monkeypatch):
    monkeypatch.setattr(module, "_worker", success_worker)
    assert module.bounded_request(settings(), b"{}") == response()
