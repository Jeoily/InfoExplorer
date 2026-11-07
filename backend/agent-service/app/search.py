"""Keyless, bounded Wikipedia retrieval. This is not a general web-search provider."""
import hashlib
import json
import socket
from datetime import datetime, timezone
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.schemas.research import Evidence, ResearchReport
from app.schemas.search_request import ResearchRequest


class SearchError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class SearchProvider(Protocol):
    def search(self, question: str) -> ResearchReport: ...


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Only the fixed provider host is fetched; returned result URLs are never fetched.
        return None


class WikipediaSearch:
    def __init__(self, language: str = "en"):
        if language not in {"en", "zh"}:
            raise ValueError("SEARCH_WIKIPEDIA_LANGUAGE must be en or zh")
        self.language = language
        self.host = f"https://{language}.wikipedia.org"

    def search(self, question: str) -> ResearchReport:
        query = question.strip()
        params = urlencode({
            "action": "query", "format": "json", "formatversion": 2,
            "generator": "search", "gsrsearch": query, "gsrnamespace": 0,
            "gsrlimit": 5, "prop": "extracts", "exintro": 1,
            "explaintext": 1, "exchars": 800, "exlimit": 5,
        })
        request = Request(f"{self.host}/w/api.php?{params}", headers={
            "User-Agent": "InfoExplorer/0.1 (local educational research prototype)",
            "Accept": "application/json",
        })
        try:
            with build_opener(NoRedirect()).open(request, timeout=20) as response:
                raw = response.read(262145)
                if len(raw) > 262144:
                    raise SearchError("SEARCH_INVALID_RESPONSE")
                payload = json.loads(raw)
        except HTTPError as error:
            error.close()
            raise SearchError("SEARCH_RATE_LIMITED" if error.code == 429 else "SEARCH_UNAVAILABLE") from None
        except (TimeoutError, socket.timeout):
            raise SearchError("SEARCH_TIMEOUT") from None
        except URLError as error:
            code = "SEARCH_TIMEOUT" if isinstance(error.reason, TimeoutError) else "SEARCH_UNAVAILABLE"
            raise SearchError(code) from None
        except (ValueError, UnicodeError):
            raise SearchError("SEARCH_INVALID_RESPONSE") from None
        return self.parse(payload, query)

    def parse(self, payload, query: str) -> ResearchReport:
        if not isinstance(payload, dict) or "error" in payload:
            raise SearchError("SEARCH_INVALID_RESPONSE")
        # MediaWiki omits query when a valid search has zero matches.
        if "query" not in payload:
            if "batchcomplete" not in payload:
                raise SearchError("SEARCH_INVALID_RESPONSE")
            pages = []
        else:
            query_result = payload["query"]
            if not isinstance(query_result, dict) or not isinstance(query_result.get("pages"), list):
                raise SearchError("SEARCH_INVALID_RESPONSE")
            pages = query_result["pages"]
        now = datetime.now(timezone.utc)
        evidence = []
        seen = set()
        if any(not isinstance(page, dict) or not isinstance(page.get("index", 0), int) for page in pages):
            raise SearchError("SEARCH_INVALID_RESPONSE")
        for page in sorted(pages, key=lambda value: value.get("index", 0)):
            if page.get("missing") is True:
                continue
            title, excerpt = page.get("title"), page.get("extract")
            if not isinstance(title, str) or not title.strip() or not isinstance(excerpt, str):
                raise SearchError("SEARCH_INVALID_RESPONSE")
            # Store plain text. No HTML execution, model instructions or arbitrary URL fetching.
            excerpt = " ".join(excerpt.split())[:800]
            if not excerpt:
                continue
            url = f"{self.host}/wiki/{quote(title.replace(' ', '_'), safe='')}"
            if url in seen:
                continue
            seen.add(url)
            evidence.append(Evidence(id=f"E{len(evidence) + 1}", url=url, title=title,
                                     excerpt=excerpt, retrievedAt=now,
                                     contentHash=hashlib.sha256(excerpt.encode("utf-8")).hexdigest()))
            if len(evidence) == 5:
                break
        if evidence:
            answer = "Wikipedia 检索资料摘要（原文摘录，未经模型分析或事实核验）：\n\n" + "\n\n".join(
                f"[{item.id}] {item.title}\n{item.excerpt}\n{item.url}" for item in evidence)
        else:
            answer = "本次 Wikipedia 检索未获得可用正文摘录。这不代表相关资料不存在，请调整关键词或语言。"
        return ResearchReport(answer=answer, sources=[item.url for item in evidence],
                              provider=f"wikipedia-{self.language}", query=query,
                              retrievedAt=now, evidence=evidence)


def get_search_provider(request: ResearchRequest) -> SearchProvider:
    # Per-request immutable instance; simultaneous languages never share mutable configuration.
    return WikipediaSearch(request.language)
