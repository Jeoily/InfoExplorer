"""HTTP contract tests against a real local Uvicorn server; no external services."""
import json
import socket
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
import uvicorn

from app.main import app
from app.search import get_search_provider, WikipediaSearch, SearchError


@pytest.fixture(scope="module")
def base_url():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                pytest.fail("Local Agent test server did not start")
            time.sleep(0.02)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
        assert not thread.is_alive(), "Agent test server did not stop"


def post(base_url, data, path="/internal/v1/agent/run"):
    request = Request(base_url + path, data=data,
                      headers={"Content-Type": "application/json"})
    try:
        response = urlopen(request, timeout=5)
    except HTTPError as error:
        response = error
    with response:
        return response.status, json.load(response)


def test_health(base_url):
    with urlopen(base_url + "/health", timeout=5) as response:
        assert response.status == 200
        assert json.load(response) == {"status": "UP"}


def test_question_and_sources(base_url):
    status, body = post(base_url, json.dumps({"question": "研究开源技术"}).encode())
    assert status == 200
    assert body == {"answer": "Python Agent received: 研究开源技术", "sources": []}


@pytest.mark.parametrize("question", [None, "", " \t\n", "a" * 4001, "😀" * 2001, 42],
                         ids=["null", "empty", "whitespace", "too-long", "emoji-too-long", "number"])
def test_invalid_question(base_url, question):
    status, body = post(base_url, json.dumps({"question": question}).encode())
    assert status == 400
    assert body["code"] == "INVALID_REQUEST"
    assert set(body) == {"code", "message"}


@pytest.mark.parametrize("data", [b"{}", b"{", b"null", b"[]"])
def test_invalid_body(base_url, data):
    assert post(base_url, data)[0] == 400


@pytest.mark.parametrize("question", ["a" * 4000, "😀" * 2000], ids=["ascii", "emoji"])
def test_boundary_length(base_url, question):
    assert post(base_url, json.dumps({"question": question}).encode())[0] == 200


def test_research_http_contract(base_url):
    class Provider:
        def search(self, question):
            return WikipediaSearch().parse({"query": {"pages": [
                {"title": "Example", "extract": "Evidence excerpt", "index": 1}]}}, question)
    app.dependency_overrides[get_search_provider] = lambda: Provider()
    try:
        status, body = post(base_url, b'{"question":"example"}', "/internal/v1/research/run")
        assert status == 200
        assert body["evidence"][0]["title"] == "Example"
        assert body["sources"] == [body["evidence"][0]["url"]]
    finally:
        app.dependency_overrides.clear()


def test_research_http_timeout_is_not_a_mock_success(base_url):
    class Provider:
        def search(self, question):
            raise SearchError("SEARCH_TIMEOUT")
    app.dependency_overrides[get_search_provider] = lambda: Provider()
    try:
        status, body = post(base_url, b'{"question":"example"}', "/internal/v1/research/run")
        assert status == 504
        assert body["code"] == "SEARCH_TIMEOUT"
        assert "answer" not in body
    finally:
        app.dependency_overrides.clear()
