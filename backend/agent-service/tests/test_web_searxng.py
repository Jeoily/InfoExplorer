"""Local HTTP emulator tests, not a deployed SearXNG or real search test."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import multiprocessing
import threading
from urllib.parse import parse_qs

import pytest

from app.web_research.pipeline import ToolFailure
from app.web_research.searxng import SearxngSearch, SearxngSettings


@pytest.fixture
def server():
    captured = []
    config = {"status": 200, "media": "application/json", "body": json.dumps({"results": [
        {"url": "https://example.org/article", "title": "Local fixture", "content": "snippet"}]}).encode()}
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            captured.append((self.path, self.headers, parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())))
            self.send_response(config["status"])
            self.send_header("Content-Type", config["media"])
            self.send_header("Content-Length", str(len(config["body"])))
            if "location" in config:
                self.send_header("Location", config["location"])
            self.end_headers()
            try:
                self.wfile.write(config["body"])
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
        def log_message(self, *args):
            pass
    service = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=service.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    try:
        yield SearxngSearch(SearxngSettings(f"http://127.0.0.1:{service.server_port}")), captured, config
    finally:
        service.shutdown()
        service.server_close()
        thread.join(timeout=2)
        assert not thread.is_alive()


def test_local_http_contract_encodes_query_without_proxy_or_credentials(server, monkeypatch):
    client, captured, config = server
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    result = client.search("后端 & format=html")
    assert len(result.candidates) == 1
    path, headers, body = captured[0]
    assert path == "/search"
    assert body["q"] == ["后端 & format=html"]
    assert body["format"] == ["json"]
    assert body["language"] == ["zh-CN"]
    assert "Authorization" not in headers
    assert "Cookie" not in headers


@pytest.mark.parametrize("status,code", [(403, "SEARCH_CONFIG_ERROR"), (429, "SEARCH_RATE_LIMITED"),
                                       (503, "SEARCH_UNAVAILABLE"), (302, "SEARCH_UNAVAILABLE")])
def test_status_errors_never_follow_redirects_or_relay_body(server, status, code):
    client, captured, config = server
    config.update(status=status, location="http://127.0.0.1:1/private", body=b"private upstream diagnostics")
    with pytest.raises(ToolFailure) as raised:
        client.search("public fixture")
    assert str(raised.value) == code
    assert len(captured) == 1


@pytest.mark.parametrize("media,body", [("text/html", b"<html>captcha</html>"),
                                      ("application/json", b"x" * 262145),
                                      ("application/json", b"{}")], ids=["html", "oversize", "bad-schema"])
def test_bad_responses_are_rejected(server, media, body):
    client, _, config = server
    config.update(media=media, body=body)
    with pytest.raises(ToolFailure, match="SEARCH_INVALID_RESPONSE"):
        client.search("public fixture")


def test_timeout_cleans_up_child_before_return(server):
    client, _, _ = server
    before = {child.pid for child in multiprocessing.active_children()}
    with pytest.raises(ToolFailure, match="SEARCH_TIMEOUT"):
        client.search("public fixture", timeout=0.0001)
    assert {child.pid for child in multiprocessing.active_children()} == before


@pytest.mark.parametrize("base", ["https://example.org", "http://localhost:8888", "http://127.0.0.1",
                                  "http://user:pass@127.0.0.1:8888", "http://127.0.0.1:8888/path",
                                  "http://127.0.0.1:8888?q=x", "http://127.0.0.1:8888#fragment",
                                  "http://192.168.1.1:8888", "http://127.0.0.1:80"])
def test_configuration_is_fixed_local_service_only(base):
    with pytest.raises(ToolFailure, match="SEARCH_CONFIG_ERROR"):
        SearxngSettings(base)
