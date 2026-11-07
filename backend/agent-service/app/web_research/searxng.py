"""Fixed local SearXNG JSON client for explicitly enabled web research routes."""
from dataclasses import dataclass
import http.client
import math
import multiprocessing
import time
from urllib.parse import urlencode, urlsplit

from app.web_research.candidates import SearchPayloadRejected, bounded_text, parse_searxng, transport_query
from app.web_research.pipeline import ToolFailure


@dataclass(frozen=True)
class SearxngSettings:
    base_url: str
    language: str = "zh-CN"

    def __post_init__(self):
        try:
            url = urlsplit(self.base_url)
            if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "::1"}
                    or url.username is not None or url.password is not None
                    or url.port is None or not 1024 <= url.port <= 65535
                    or url.path not in {"", "/"} or url.query or url.fragment
                    or any(ord(char) <= 32 for char in self.base_url)
                    or self.language not in {"zh-CN", "en-US"}):
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise ToolFailure("SEARCH_CONFIG_ERROR") from None


def _http_query(settings: SearxngSettings, query: str, timeout: float) -> bytes:
    url = urlsplit(settings.base_url)
    connection = http.client.HTTPConnection(url.hostname, url.port, timeout=timeout)
    try:
        body = urlencode({"q": transport_query(query), "format": "json", "language": settings.language,
                          "categories": "general", "pageno": 1, "safesearch": 1}).encode("ascii")
        connection.request("POST", "/search", body=body, headers={
            "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json",
            "Accept-Encoding": "identity", "User-Agent": "InfoExplorer/0.1 local research client",
        })
        response = connection.getresponse()
        if response.status != 200:
            code = {429: "SEARCH_RATE_LIMITED", 403: "SEARCH_CONFIG_ERROR"}.get(response.status, "SEARCH_UNAVAILABLE")
            raise ToolFailure(code)
        if (response.getheader("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json"
                or response.getheader("Content-Encoding", "identity").lower() not in {"", "identity"}):
            raise ToolFailure("SEARCH_INVALID_RESPONSE")
        raw = response.read(262145)
        if len(raw) > 262144:
            raise ToolFailure("SEARCH_INVALID_RESPONSE")
        return raw
    finally:
        connection.close()


def _search_worker(sender, settings, query, timeout):
    try:
        sender.send((None, _http_query(settings, query, timeout)))
    except ToolFailure as error:
        sender.send((error.code, None))
    except TimeoutError:
        sender.send(("SEARCH_TIMEOUT", None))
    except Exception:
        sender.send(("SEARCH_UNAVAILABLE", None))
    finally:
        sender.close()


class SearxngSearch:
    def __init__(self, settings: SearxngSettings):
        self.settings = settings

    def search(self, query: str, timeout: float = 20.0):
        query = bounded_text(query, 4000)
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 20:
            raise ValueError("Invalid search timeout")
        context = multiprocessing.get_context("spawn")
        receiver, sender = context.Pipe(duplex=False)
        process = context.Process(target=_search_worker, args=(sender, self.settings, query, timeout), daemon=True)
        deadline = time.monotonic() + timeout
        try:
            process.start()
            sender.close()
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not receiver.poll(remaining):
                raise ToolFailure("SEARCH_TIMEOUT")
            code, raw = receiver.recv()
            if time.monotonic() >= deadline:
                raise ToolFailure("SEARCH_TIMEOUT")
            if code is not None:
                raise ToolFailure(code)
            return parse_searxng(raw, query=query)
        except SearchPayloadRejected:
            raise ToolFailure("SEARCH_INVALID_RESPONSE") from None
        except (EOFError, OSError):
            raise ToolFailure("SEARCH_UNAVAILABLE") from None
        finally:
            sender.close()
            receiver.close()
            if process.pid is not None:
                process.join(timeout=0.1)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=2)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=2)
                process.close()
