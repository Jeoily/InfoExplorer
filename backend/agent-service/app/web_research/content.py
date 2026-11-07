"""Download and extract with one deadline; no API route enables this implicitly."""
from dataclasses import replace
import hashlib
import json
import math
import time

from app.web_research.download import DownloadError, download_html
from app.web_research.extraction import ExtractionError, extract_html
from app.web_research.pipeline import ToolFailure
from app.web_research.selection import SourceMetadata
from app.web_research.url_policy import UrlRejected, validate_candidate_url


def read_content(candidate, timeout=20.0):
    """ContentTool adapter. Extracted dates are unverified metadata, not event dates.

    Hash covers the retained normalized paragraphs, not the full downloaded page.
    Source identity remains the discovered candidate; redirect destination is
    recorded separately and never obtained from HTML canonical metadata.
    """
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Invalid content timeout")
    deadline = time.monotonic() + min(timeout, 20.0)

    def remaining():
        value = deadline - time.monotonic()
        if value <= 0:
            raise ToolFailure("CONTENT_TIMEOUT")
        return value

    try:
        page = download_html(candidate, remaining())
        remaining()
        if page.requested_url != candidate.requested_url:
            raise ToolFailure("CONTENT_INVALID_RESPONSE")
        final = validate_candidate_url(page.resolved_url)
        extracted = extract_html(candidate, page.html, content_type=page.content_type,
                                 timeout=remaining())
        remaining()
        document = extracted.document
        if document.source_id != candidate.source_id or document.host != candidate.host:
            raise ToolFailure("CONTENT_INVALID_RESPONSE")
        # JSON array encoding preserves paragraph boundaries without delimiter ambiguity.
        encoded = json.dumps(document.paragraphs, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        metadata = SourceMetadata(page.requested_url, final.requested_url, final.host,
            page.retrieved_at, page.content_type, page.http_requests, extracted.extractor,
            extracted.published_text, "extractor_unverified" if extracted.published_text else "unknown",
            extracted.truncated, hashlib.sha256(encoded).hexdigest())
        remaining()
        return replace(document, metadata=metadata)
    except (DownloadError, ExtractionError, UrlRejected) as error:
        # Only fixed internal codes cross into the coordinator, never exception text.
        try:
            failure = ToolFailure(error.code)
        except ValueError:
            failure = ToolFailure("CONTENT_UNAVAILABLE")
        raise failure from None
