import hashlib
import io
import os
import json
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import pytest

from app.search import SearchError, WikipediaSearch
import app.search as search_module


def payload():
    return {"batchcomplete": True, "query": {"pages": [
        {"index": 2, "title": "Second", "extract": "Second excerpt"},
        {"index": 1, "title": "Artificial intelligence", "extract": "First\n excerpt"},
        {"index": 3, "title": "Artificial intelligence", "extract": "duplicate"},
    ]}}


def test_rank_deduplication_and_hash():
    report = WikipediaSearch().parse(payload(), "AI")
    assert len(report.evidence) == 2
    first = report.evidence[0]
    assert first.id == "E1"
    assert first.url == "https://en.wikipedia.org/wiki/Artificial_intelligence"
    assert first.excerpt == "First excerpt"
    assert first.contentHash == hashlib.sha256(first.excerpt.encode()).hexdigest()
    assert report.sources == [e.url for e in report.evidence]
    assert "[E1]" in report.answer
    assert report.retrievedAt.tzinfo is not None


def test_empty_results_are_not_fabricated():
    report = WikipediaSearch().parse({"batchcomplete": True}, "no results")
    assert report.evidence == []
    assert report.sources == []
    assert "不代表" in report.answer


@pytest.mark.parametrize("data", [{}, [], {"error": {}}, {"query": {}},
                                  {"query": {"pages": [None]}},
                                  {"query": {"pages": [{"title": "bad", "extract": None}]}}])
def test_invalid_responses(data):
    with pytest.raises(SearchError, match="SEARCH_INVALID_RESPONSE"):
        WikipediaSearch().parse(data, "query")


def test_bounded_excerpts_and_result_count():
    pages = [{"index": i, "title": f"Title {i}", "extract": "a" * 3000} for i in range(8)]
    report = WikipediaSearch().parse({"query": {"pages": pages}}, "query")
    assert len(report.evidence) == 5
    assert all(len(e.excerpt) == 800 for e in report.evidence)


def test_transport_uses_fixed_host_and_encodes_query(monkeypatch):
    class Opener:
        def open(self, request, timeout):
            parsed = urlsplit(request.full_url)
            assert parsed.netloc == "en.wikipedia.org"
            assert parse_qs(parsed.query)["gsrsearch"] == ["query & unsafe=http://127.0.0.1"]
            assert timeout == 20
            return io.BytesIO(json.dumps(payload()).encode())
    monkeypatch.setattr(search_module, "build_opener", lambda *args: Opener())
    assert len(WikipediaSearch().search("query & unsafe=http://127.0.0.1").evidence) == 2


@pytest.mark.parametrize("error,code", [
    (TimeoutError(), "SEARCH_TIMEOUT"),
    (URLError("private network details"), "SEARCH_UNAVAILABLE"),
    (HTTPError("https://example.org", 429, "limited", {}, None), "SEARCH_RATE_LIMITED"),
])
def test_transport_errors_are_safe(monkeypatch, error, code):
    class Opener:
        def open(self, request, timeout):
            raise error
    monkeypatch.setattr(search_module, "build_opener", lambda *args: Opener())
    with pytest.raises(SearchError, match=code):
        WikipediaSearch().search("query")


def test_response_size_limit(monkeypatch):
    class Opener:
        def open(self, request, timeout):
            return io.BytesIO(b"x" * 262145)
    monkeypatch.setattr(search_module, "build_opener", lambda *args: Opener())
    with pytest.raises(SearchError, match="SEARCH_INVALID_RESPONSE"):
        WikipediaSearch().search("query")


def test_language_allowlist():
    with pytest.raises(ValueError):
        WikipediaSearch("localhost")


@pytest.mark.skipif(os.environ.get("INFOEXPLORER_LIVE_SEARCH") != "1", reason="Live internet search is opt-in")
def test_live_wikipedia():
    report = WikipediaSearch().search("artificial intelligence")
    assert report.provider == "wikipedia-en"
    assert report.evidence
    assert all(e.url.startswith("https://en.wikipedia.org/wiki/") for e in report.evidence)
