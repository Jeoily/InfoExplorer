"""Conservative public HTML downloader, isolated from live API routes.

Only identity-encoded static HTML is supported. DNS and every redirect are
checked; sockets connect to a validated numeric IP, TLS verifies the URL host.
No cookies, proxies, browser state, authentication or JavaScript are used.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import http.client
import ipaddress
import math
import multiprocessing
import socket
import ssl
import threading
import time
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from app.web_research.candidates import Candidate
from app.web_research.url_policy import UrlRejected, validate_candidate_url, validate_resolved_ips

USER_AGENT = "InfoExplorerBot/0.1"
_GATE = threading.Lock()
_NEXT_REQUEST = 0.0


class DownloadError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class DownloadedPage:
    requested_url: str
    resolved_url: str
    html: bytes
    content_type: str
    retrieved_at: str
    http_requests: int


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str]
    body: bytes


def _remaining(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise DownloadError("CONTENT_TIMEOUT")
    return remaining


def _resolve(host, port):
    return validate_resolved_ips(tuple(item[4][0] for item in
        socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)))


class _PinnedConnection(http.client.HTTPConnection):
    def __init__(self, host, port, address, timeout, secure):
        super().__init__(host, port, timeout=timeout)
        self.address, self.secure = address, secure

    def connect(self):
        address = ipaddress.ip_address(self.address)
        raw = socket.socket(socket.AF_INET6 if address.version == 6 else socket.AF_INET, socket.SOCK_STREAM)
        try:
            raw.settimeout(self.timeout)
            raw.connect((str(address), self.port))
            if ipaddress.ip_address(raw.getpeername()[0]) != address:
                raise DownloadError("SOURCE_ADDRESS_REJECTED")
            self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=self.host) if self.secure else raw
        except BaseException:
            raw.close()
            raise


def _request(url, limit, deadline):
    checked = validate_candidate_url(url)
    addresses = _resolve(checked.host, checked.port)
    # No implicit retry against another IP. An unavailable first address is a
    # visible failure rather than an unaccounted extra network attempt.
    connection = _PinnedConnection(checked.host, checked.port, addresses[0],
                                   _remaining(deadline), urlsplit(url).scheme == "https")
    try:
        parsed = urlsplit(checked.requested_url)
        target = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
        if parsed.query:
            target += "?" + quote(parsed.query, safe="/%?:@!$&'()*+,;=-._~")
        connection.request("GET", target, headers={"User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,text/plain", "Accept-Encoding": "identity",
            "Connection": "close"})
        reply = connection.getresponse()
        headers = {key.lower(): value.strip() for key, value in reply.getheaders()}
        # Ambiguous framing/redirect metadata is rejected rather than guessed.
        for key in ("content-length", "transfer-encoding", "location", "content-type", "content-encoding"):
            if len(reply.headers.get_all(key, [])) > 1:
                raise DownloadError("CONTENT_INVALID_RESPONSE")
        if headers.get("content-encoding", "identity").lower() not in {"", "identity"}:
            raise DownloadError("CONTENT_UNSUPPORTED_ENCODING")
        size = headers.get("content-length")
        if size is not None and (not size.isascii() or not size.isdecimal() or int(size) > limit):
            raise DownloadError("CONTENT_TOO_LARGE")
        if size is not None and "transfer-encoding" in headers:
            raise DownloadError("CONTENT_INVALID_RESPONSE")
        if headers.get("transfer-encoding", "").lower() not in {"", "chunked"}:
            raise DownloadError("CONTENT_INVALID_RESPONSE")
        # No need to consume a redirect/error body. Its content cannot become evidence.
        if reply.status != 200:
            return Response(reply.status, headers, b"")
        parts, count = [], 0
        while True:
            _remaining(deadline)
            chunk = reply.read(min(65536, limit + 1 - count))
            if not chunk:
                break
            count += len(chunk)
            if count > limit:
                raise DownloadError("CONTENT_TOO_LARGE")
            parts.append(chunk)
        if size is not None and count != int(size):
            raise DownloadError("CONTENT_INVALID_RESPONSE")
        return Response(reply.status, headers, b"".join(parts))
    finally:
        connection.close()


def _download(url, timeout, request=_request):
    """Pure orchestration is injectable for offline malicious-response fixtures."""
    deadline = time.monotonic() + timeout
    original = validate_candidate_url(url).requested_url
    requests = 0
    robots = {}
    next_fetch = 0.0

    def fetch(address, limit):
        nonlocal requests, next_fetch
        _remaining(deadline)
        validate_candidate_url(address)
        if requests >= 12:
            raise DownloadError("CONTENT_REQUEST_LIMIT")
        pause = max(0, next_fetch - time.monotonic())
        if pause >= _remaining(deadline):
            raise DownloadError("CONTENT_TIMEOUT")
        if pause:
            time.sleep(pause)
        requests += 1
        try:
            return request(address, limit, deadline)
        finally:
            next_fetch = time.monotonic() + 0.25

    def follow(address, limit):
        seen = set()
        for _ in range(4):
            checked = validate_candidate_url(address)
            address = checked.requested_url
            if address in seen:
                raise DownloadError("CONTENT_REDIRECT_REJECTED")
            seen.add(address)
            response = fetch(address, limit)
            if response.status not in {301, 302, 303, 307, 308}:
                return address, response
            destination = urljoin(address, response.headers.get("location", ""))
            if not response.headers.get("location") or (address.startswith("https:") and not destination.startswith("https:")):
                raise DownloadError("CONTENT_REDIRECT_REJECTED")
            address = validate_candidate_url(destination).requested_url
        raise DownloadError("CONTENT_REDIRECT_REJECTED")

    def allowed(address):
        parsed = urlsplit(address)
        origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
        if origin not in robots:
            _, response = follow(origin + "/robots.txt", 512 * 1024)
            if response.status in {404, 410}:
                robots[origin] = None
            elif response.status == 200:
                media = response.headers.get("content-type", "").split(";", 1)[0].lower()
                if media != "text/plain":
                    raise DownloadError("CONTENT_ROBOTS_UNAVAILABLE")
                try:
                    text = response.body.decode("utf-8-sig")
                except UnicodeError:
                    raise DownloadError("CONTENT_ROBOTS_UNAVAILABLE") from None
                # urllib.robotparser does not implement RFC 9309 wildcard/$
                # matching. Reject these files rather than accidentally allowing.
                prohibitions = []
                for line in text.splitlines():
                    directive, _, value = line.partition(":")
                    directive = directive.strip().lower()
                    value = value.split("#")[0].strip()
                    if directive in {"allow", "disallow"} and any(c in value for c in "*$"):
                        raise DownloadError("CONTENT_ROBOTS_UNSUPPORTED")
                    if directive in {"crawl-delay", "request-rate"} and value:
                        raise DownloadError("CONTENT_ROBOTS_UNSUPPORTED")
                    if directive == "disallow" and value:
                        prohibitions.append("Disallow: " + value)
                parser = RobotFileParser()
                # Conservative subset: merge prohibitions from ALL groups and
                # do not apply Allow exceptions. This can over-block, never claim
                # full RFC 9309 compatibility or bypass a more-specific group.
                parser.parse(["User-agent: *", *prohibitions])
                robots[origin] = parser
            else:
                raise DownloadError("CONTENT_ROBOTS_UNAVAILABLE")
        parser = robots[origin]
        if parser is not None:
            if not parser.can_fetch(USER_AGENT, address):
                raise DownloadError("CONTENT_DISALLOWED")
            delay = parser.crawl_delay(USER_AGENT)
            rate = parser.request_rate(USER_AGENT)
            if delay or rate:
                # Cross-request crawl scheduling is not yet implemented.
                raise DownloadError("CONTENT_ROBOTS_UNSUPPORTED")

    address, seen = original, set()
    for _ in range(4):
        address = validate_candidate_url(address).requested_url
        if address in seen:
            raise DownloadError("CONTENT_REDIRECT_REJECTED")
        seen.add(address)
        allowed(address)  # Recheck path and origin BEFORE each redirected request.
        response = fetch(address, 2 * 1024 * 1024)
        if response.status in {301, 302, 303, 307, 308}:
            destination = urljoin(address, response.headers.get("location", ""))
            if not response.headers.get("location") or (address.startswith("https:") and not destination.startswith("https:")):
                raise DownloadError("CONTENT_REDIRECT_REJECTED")
            address = validate_candidate_url(destination).requested_url
            continue
        if response.status != 200:
            raise DownloadError("CONTENT_UNAVAILABLE")
        media = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if media not in {"text/html", "application/xhtml+xml"}:
            raise DownloadError("CONTENT_UNSUPPORTED")
        if not response.body:
            raise DownloadError("CONTENT_EMPTY")
        _remaining(deadline)
        return DownloadedPage(original, address, response.body, media,
                              datetime.now(timezone.utc).isoformat(), requests)
    raise DownloadError("CONTENT_REDIRECT_REJECTED")


def _worker(sender, url, timeout):
    try:
        sender.send((None, _download(url, timeout)))
    except (DownloadError, UrlRejected) as error:
        sender.send((error.code, None))
    except TimeoutError:
        sender.send(("CONTENT_TIMEOUT", None))
    except Exception:
        sender.send(("CONTENT_UNAVAILABLE", None))
    finally:
        sender.close()


def download_html(candidate: Candidate, timeout: float = 20.0) -> DownloadedPage:
    """Parent deadline includes DNS, TLS and child startup; no automatic retries.

    Process-local serialization is not a cross-process/domain rate limiter.
    Failures and cleanup may consume time beyond the request deadline.
    """
    global _NEXT_REQUEST
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 20:
        raise ValueError("Invalid download timeout")
    checked = validate_candidate_url(candidate.requested_url)
    if checked.canonical_url != candidate.canonical_url or checked.host != candidate.host:
        raise DownloadError("CONTENT_INVALID_RESPONSE")
    deadline = time.monotonic() + timeout
    if not _GATE.acquire(timeout=timeout):
        raise DownloadError("CONTENT_TIMEOUT")
    receiver = sender = process = None
    try:
        context = multiprocessing.get_context("spawn")
        receiver, sender = context.Pipe(duplex=False)
        process = context.Process(target=_worker, args=(sender, checked.requested_url, timeout), daemon=True)
        pause = max(0, _NEXT_REQUEST - time.monotonic())
        if pause >= _remaining(deadline):
            raise DownloadError("CONTENT_TIMEOUT")
        if pause:
            time.sleep(pause)
        process.start()
        sender.close()
        if not receiver.poll(_remaining(deadline)):
            raise DownloadError("CONTENT_TIMEOUT")
        code, page = receiver.recv()
        _remaining(deadline)
        if code:
            raise DownloadError(code)
        return page
    except (EOFError, OSError):
        raise DownloadError("CONTENT_UNAVAILABLE") from None
    finally:
        try:
            if sender is not None:
                sender.close()
            if receiver is not None:
                receiver.close()
            if process is not None and process.pid is not None:
                process.join(timeout=0.1)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=2)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=2)
                process.close()
        finally:
            _NEXT_REQUEST = time.monotonic() + 0.5
            _GATE.release()
