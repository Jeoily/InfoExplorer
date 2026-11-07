"""Bounded SearXNG JSON interpretation; search snippets are NOT evidence."""
from dataclasses import dataclass
import hashlib
import json
import re
from urllib.parse import urlsplit

from app.web_research.url_policy import UrlRejected, validate_candidate_url


class SearchPayloadRejected(Exception):
    def __init__(self):
        super().__init__("SEARCH_INVALID_RESPONSE")


def utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def bounded_text(value: object, limit: int, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError("Invalid text")
    if any(0xD800 <= ord(ch) <= 0xDFFF or ord(ch) == 0 for ch in value):
        raise ValueError("Invalid text")
    normalized = " ".join(value.split())
    if (not normalized and not allow_empty) or utf16_length(normalized) > limit:
        raise ValueError("Invalid text")
    return normalized


@dataclass(frozen=True)
class Candidate:
    source_id: str
    requested_url: str
    canonical_url: str
    host: str
    title: str
    snippet: str
    rank: int
    engines: tuple[str, ...]
    published_text: str | None


@dataclass(frozen=True)
class SearchBatch:
    candidates: tuple[Candidate, ...]
    rejected_count: int
    duplicate_count: int
    truncated: bool
    warnings: tuple[str, ...]


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def query_site_scope(query: str) -> tuple[str, str, str] | None:
    """Recognize one positive site:domain[/path] query, not Boolean syntax.

    This is a retrieval relevance filter, not a general query parser or an
    assertion that a host is authoritative. Full URLs and escaped paths are excluded.
    """
    if re.search(r'["()|]|\bOR\b', query):
        return None
    operators = re.findall(r'(?<!\S)(-?site:\S+)', query, re.I)
    if len(operators) != 1 or operators[0].startswith('-'):
        return None
    target = operators[0][5:]
    if not re.fullmatch(r'[a-zA-Z0-9.-]+(?:/[a-zA-Z0-9._~/-]*)?', target):
        return None
    try:
        url = validate_candidate_url('https://' + target)
        return url.host, urlsplit(url.canonical_url).path, operators[0]
    except UrlRejected:
        return None


def query_site_host(query: str) -> str | None:
    scope = query_site_scope(query)
    return scope[0] if scope else None


def transport_query(query: str) -> str:
    """Search by domain; enforce the original path scope on returned URLs.

    Some upstreams return nothing for site:domain/path. This translation does
    not widen accepted results and does not issue an additional request.
    """
    scope = query_site_scope(query)
    if not scope or scope[1] in {'', '/'}:
        return query
    host, path, operator = scope
    converted = query.replace(operator, 'site:' + host, 1)
    if converted.strip() == 'site:' + host:
        basename = path.rstrip('/').rsplit('/', 1)[-1]
        converted += ' ' + basename
    return converted


def parse_searxng(raw: bytes, *, max_results: int = 5, query: str = '') -> SearchBatch:
    """Parse an already size-bounded response; no HTTP, DNS or model access.

    At most 100 raw results are examined. All-malformed results are a provider
    error, whereas valid URLs rejected by policy are a valid but unusable batch.
    """
    if type(max_results) is not int or not 1 <= max_results <= 10:
        raise ValueError("Invalid result limit")
    try:
        if not isinstance(raw, bytes) or len(raw) > 262144:
            raise ValueError()
        scope = query_site_scope(query)
        data = json.loads(raw, object_pairs_hook=_unique_keys,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            raise ValueError()
        results = data["results"]
        if len(results) > 100:
            raise ValueError()
        engine_failures = data.get("unresponsive_engines", [])
        if not isinstance(engine_failures, list) or len(engine_failures) > 100:
            raise ValueError()
        warnings = ("SEARCH_ENGINES_PARTIALLY_UNAVAILABLE",) if engine_failures else ()
        candidates = []
        seen = set()
        rejected = duplicates = malformed = 0
        truncated = False
        for rank, entry in enumerate(results, start=1):
            try:
                if not isinstance(entry, dict):
                    raise ValueError()
                title = bounded_text(entry.get("title"), 512)
                snippet = bounded_text(entry.get("content", ""), 4000, allow_empty=True)
                if not isinstance(entry.get("url"), str):
                    raise ValueError()
                engines = entry.get("engines", [])
                if (not isinstance(engines, list) or len(engines) > 50
                        or any(not isinstance(e, str) or not re.fullmatch(r"[a-zA-Z0-9_. -]{1,80}", e)
                               for e in engines)):
                    raise ValueError()
                published = entry.get("publishedDate")
                if published is not None:
                    published = bounded_text(published, 100)
                url = validate_candidate_url(entry["url"])
            except UrlRejected:
                rejected += 1
                continue
            except (ValueError, TypeError, UnicodeError):
                rejected += 1
                malformed += 1
                continue
            if scope:
                required_host, path, _ = scope
                actual_path = urlsplit(url.canonical_url).path
                if (not (url.host == required_host or url.host.endswith('.' + required_host))
                        or (path not in {'', '/'} and actual_path != path
                            and not actual_path.startswith(path.rstrip('/') + '/'))):
                    rejected += 1
                    continue
            if url.canonical_url in seen:
                duplicates += 1
                continue
            seen.add(url.canonical_url)
            if len(candidates) == max_results:
                truncated = True
                continue
            candidates.append(Candidate(
                "S" + hashlib.sha256(url.canonical_url.encode("utf-8")).hexdigest(),
                url.requested_url, url.canonical_url, url.host, title, snippet, rank,
                tuple(dict.fromkeys(engines)), published))
        if results and malformed == len(results):
            raise ValueError()
        return SearchBatch(tuple(candidates), rejected, duplicates, truncated, warnings)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise SearchPayloadRejected() from None
