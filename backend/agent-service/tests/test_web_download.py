import socket
import threading
from unittest.mock import Mock

import pytest

from app.web_research import download as d
from app.web_research.url_policy import UrlRejected
from app.web_research.candidates import parse_searxng


def test_process_setup_failure_does_not_lock_out_later_downloads(monkeypatch):
    gate = threading.Lock()
    monkeypatch.setattr(d, "_GATE", gate)
    monkeypatch.setattr(d.multiprocessing, "get_context", Mock(side_effect=OSError("fixture")))
    candidate = parse_searxng(b'{"results": [{"url": "https://example.org/article", "title": "Fixture"}]}')
    with pytest.raises(d.DownloadError, match="CONTENT_UNAVAILABLE"):
        d.download_html(candidate.candidates[0])
    assert gate.acquire(blocking=False)
    gate.release()


def response(status=200, body=b"<html>public fixture</html>", **headers):
    return d.Response(status, {"content-type": "text/html", **headers}, body)


def run_fixture(pages, url="https://example.org/article"):
    calls = []
    def request(url, limit, deadline):
        calls.append(url)
        if url.endswith("/robots.txt") and url not in pages:
            return response(404)
        return pages[url]
    return d._download(url, 10, request), calls


def test_public_html_keeps_actual_final_url_and_request_count():
    result, calls = run_fixture({"https://example.org/article": response(302, location="/final"),
                                 "https://example.org/final": response()})
    assert result.requested_url.endswith("/article")
    assert result.resolved_url.endswith("/final")
    assert result.http_requests == 3
    assert calls == ["https://example.org/robots.txt", "https://example.org/article", "https://example.org/final"]


@pytest.mark.parametrize("target", ["http://127.0.0.1/private", "https://192.168.1.1/", "file:///private",
                                  "https://user:password@example.org/", "https://example.org:444/", "http://example.org/"])
def test_redirect_never_reaches_unsafe_target(target):
    calls = []
    def request(url, limit, deadline):
        calls.append(url)
        return response(404) if url.endswith("/robots.txt") else response(302, location=target)
    with pytest.raises((d.DownloadError, UrlRejected)):
        d._download("https://example.org/article", 10, request)
    assert len(calls) == 2


def test_redirect_new_host_must_pass_its_robots_before_content():
    pages = {"https://example.org/article": response(302, location="https://example.net/private"),
             "https://example.net/robots.txt": response(body=b"User-agent: *\nDisallow: /private", **{"content-type": "text/plain"})}
    with pytest.raises(d.DownloadError, match="CONTENT_DISALLOWED"):
        run_fixture(pages)


@pytest.mark.parametrize("body", [b"User-agent: *\nDisallow: /", b"User-agent: *\nAllow: /\nDisallow: /article",
                                  b"User-agent: *\nDisallow:\nDisallow: /article",
                                  b"User-agent: other\nDisallow: /article\nUser-agent: *\nDisallow:"])
def test_robots_conservatively_preserves_prohibitions(body):
    with pytest.raises(d.DownloadError, match="CONTENT_DISALLOWED"):
        run_fixture({"https://example.org/robots.txt": response(body=body, **{"content-type": "text/plain"})})


@pytest.mark.parametrize("directive", [b"Disallow: /*secret", b"Allow: /public$", b"Crawl-delay: 2", b"Request-rate: 1/10"])
def test_unsupported_robots_does_not_silently_allow(directive):
    with pytest.raises(d.DownloadError, match="CONTENT_ROBOTS_UNSUPPORTED"):
        run_fixture({"https://example.org/robots.txt": response(body=b"User-agent: *\n" + directive, **{"content-type": "text/plain"})})


@pytest.mark.parametrize("status", [401, 403, 429, 503])
def test_robots_failure_is_closed(status):
    with pytest.raises(d.DownloadError, match="CONTENT_ROBOTS_UNAVAILABLE"):
        run_fixture({"https://example.org/robots.txt": response(status)})


def test_robots_redirect_to_localhost_rejected_before_request():
    with pytest.raises(UrlRejected):
        run_fixture({"https://example.org/robots.txt": response(302, location="https://127.0.0.1/")})


def test_empty_robots_allows_public_html():
    result, _ = run_fixture({"https://example.org/robots.txt": response(body=b"", **{"content-type": "text/plain"}),
                             "https://example.org/article": response()})
    assert result.html


def test_redirect_loop_is_bounded():
    with pytest.raises(d.DownloadError, match="CONTENT_REDIRECT_REJECTED"):
        run_fixture({"https://example.org/article": response(302, location="/article")})


@pytest.mark.parametrize("media,body,code", [("application/pdf", b"pdf", "CONTENT_UNSUPPORTED"),
                                           ("text/html", b"", "CONTENT_EMPTY")])
def test_only_nonempty_html_is_evidence_input(media, body, code):
    with pytest.raises(d.DownloadError, match=code):
        run_fixture({"https://example.org/article": response(body=body, **{"content-type": media})})


def test_mixed_public_and_private_dns_is_rejected(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in ("93.184.216.34", "127.0.0.1")])
    with pytest.raises(UrlRejected, match="SOURCE_ADDRESS_REJECTED"):
        d._resolve("example.org", 443)


def test_connect_pins_numeric_address_but_tls_verifies_original_host(monkeypatch):
    raw, context = Mock(), Mock()
    raw.getpeername.return_value = ("93.184.216.34", 443)
    monkeypatch.setattr(d.socket, "socket", lambda *a: raw)
    monkeypatch.setattr(d.ssl, "create_default_context", lambda: context)
    connection = d._PinnedConnection("example.org", 443, "93.184.216.34", 3, True)
    connection.connect()
    raw.connect.assert_called_once_with(("93.184.216.34", 443))
    context.wrap_socket.assert_called_once_with(raw, server_hostname="example.org")
    assert connection.sock == context.wrap_socket.return_value


def test_peer_mismatch_closes_socket_before_tls(monkeypatch):
    raw = Mock()
    raw.getpeername.return_value = ("127.0.0.1", 443)
    monkeypatch.setattr(d.socket, "socket", lambda *a: raw)
    with pytest.raises(d.DownloadError, match="SOURCE_ADDRESS_REJECTED"):
        d._PinnedConnection("example.org", 443, "93.184.216.34", 3, True).connect()
    raw.close.assert_called_once()


@pytest.mark.parametrize("headers,code", [({"Content-Encoding": "gzip"}, "CONTENT_UNSUPPORTED_ENCODING"),
    ({"Content-Length": "3000000"}, "CONTENT_TOO_LARGE"),
    ({"Content-Length": "1", "Transfer-Encoding": "chunked"}, "CONTENT_INVALID_RESPONSE"),
    ({"Transfer-Encoding": "weird"}, "CONTENT_INVALID_RESPONSE")])
def test_transport_rejects_unbounded_or_ambiguous_body(monkeypatch, headers, code):
    from email.message import Message
    message = Message()
    for key, value in headers.items():
        message[key] = value
    reply = Mock(status=200, headers=message)
    reply.getheaders.return_value = list(message.items())
    connection = Mock()
    connection.getresponse.return_value = reply
    monkeypatch.setattr(d, "_resolve", lambda *a: ("93.184.216.34",))
    monkeypatch.setattr(d, "_PinnedConnection", lambda *a: connection)
    with pytest.raises(d.DownloadError, match=code):
        d._request("https://example.org/article", 2 * 1024 * 1024, d.time.monotonic() + 2)
    reply.read.assert_not_called()
    connection.close.assert_called_once()


@pytest.mark.parametrize("declared,body,code", [(None, b"12345", "CONTENT_TOO_LARGE"),
    ("4", b"12", "CONTENT_INVALID_RESPONSE")])
def test_actual_stream_length_is_checked_not_only_headers(monkeypatch, declared, body, code):
    import io
    from email.message import Message
    message = Message()
    message["Content-Type"] = "text/html"
    if declared is not None:
        message["Content-Length"] = declared
    reply = Mock(status=200, headers=message)
    reply.getheaders.return_value = list(message.items())
    reply.read.side_effect = io.BytesIO(body).read
    connection = Mock()
    connection.getresponse.return_value = reply
    monkeypatch.setattr(d, "_resolve", lambda *a: ("93.184.216.34",))
    monkeypatch.setattr(d, "_PinnedConnection", lambda *a: connection)
    with pytest.raises(d.DownloadError, match=code):
        d._request("https://example.org/article", 4, d.time.monotonic() + 2)
    connection.close.assert_called_once()


def test_duplicate_transfer_encoding_is_rejected_before_body(monkeypatch):
    from email.message import Message
    message = Message()
    message["Transfer-Encoding"] = "chunked"
    message["Transfer-Encoding"] = "chunked"
    reply = Mock(status=200, headers=message)
    reply.getheaders.return_value = list(message.items())
    connection = Mock()
    connection.getresponse.return_value = reply
    monkeypatch.setattr(d, "_resolve", lambda *a: ("93.184.216.34",))
    monkeypatch.setattr(d, "_PinnedConnection", lambda *a: connection)
    with pytest.raises(d.DownloadError, match="CONTENT_INVALID_RESPONSE"):
        d._request("https://example.org/article", 100, d.time.monotonic() + 2)
    reply.read.assert_not_called()
    connection.close.assert_called_once()
